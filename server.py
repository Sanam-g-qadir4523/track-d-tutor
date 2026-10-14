import json
import os
import random
import sys
import time
import uuid

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastembed import TextEmbedding
from google import genai
from google.genai import types
from pydantic import BaseModel

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

BASE = "http://localhost:8000"
MODEL = "gemini-3.5-flash-lite"
MIN_SCORE = 0.60  # andazi hadd, evaluation mein jaanch kar theek karenge
N_VIDEO, N_SLIDES = 4, 3
SIM_LIMIT = 0.88  # andazi hadd (repeat sawal)
P_INIT, P_LEARN, P_GUESS, P_SLIP = 0.30, 0.15, 0.25, 0.10  # BKT: andazi values
TOPICS = {1: "Basics", 2: "Perceptrons", 3: "Features",
          4: "Logistic regression", 5: "Regression"}
HISTORY = "data/quiz_history.json"
ANSWERS = "data/answers.json"
REFUSAL = {
    "en": ("This is not covered in the course material (Lectures 1-5), "
           "so I can't answer it from the sources."),
    "ur": ("یہ سوال کورس کے مواد (لیکچر 1 سے 5) میں شامل نہیں ہے، "
           "اس لیے سورسز کی بنیاد پر اس کا جواب نہیں دیا جا سکتا۔"),
}

app = FastAPI(title="Track D Tutor API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


with open("data/chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)
emb = np.load("data/embeddings.npy")
emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
embedder = TextEmbedding("BAAI/bge-small-en-v1.5")
history = load(HISTORY)
answers = load(ANSWERS)
PENDING = {}


def embed_text(text):
    v = np.array(list(embedder.embed([text]))[0], dtype="float32")
    return v / np.linalg.norm(v)


hist_vecs = [embed_text(h["question"]) for h in history]


def call_json(prompt):
    r = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(r.text)


def link(c):
    if c["type"] == "video":
        return c["url"]
    return f"{BASE}/slides/{c['lecture']}#page={c['slide']}"


def search(question):
    q = np.array(list(embedder.query_embed(question))[0], dtype="float32")
    q = q / np.linalg.norm(q)
    scores = emb @ q
    order = scores.argsort()[::-1]
    video = [i for i in order if chunks[i]["type"] == "video"][:N_VIDEO]
    slides = [i for i in order
              if chunks[i]["type"] == "slide" and len(chunks[i]["text"]) >= 40][:N_SLIDES]
    picked = sorted(video + slides, key=lambda i: -scores[i])
    return [(chunks[i], float(scores[i])) for i in picked]


def bkt_update(p, correct):
    if correct:
        post = p * (1 - P_SLIP) / (p * (1 - P_SLIP) + (1 - p) * P_GUESS)
    else:
        post = p * P_SLIP / (p * P_SLIP + (1 - p) * (1 - P_GUESS))
    return post + (1 - post) * P_LEARN


def state():
    mastery, counts, rights = {}, {}, {}
    for a in answers:
        t = a["topic"]
        mastery.setdefault(t, P_INIT)
        counts[t] = counts.get(t, 0) + 1
        rights[t] = rights.get(t, 0) + int(a["correct"])
        mastery[t] = bkt_update(mastery[t], a["correct"])
    return mastery, counts, rights


def choose_lecture():
    mastery, counts, _ = state()
    untested = [n for n, t in TOPICS.items() if counts.get(t, 0) == 0]
    if untested:
        return random.choice(untested), "easy", "Diagnostic: topic not tested yet"
    n = min(TOPICS, key=lambda k: mastery[TOPICS[k]])
    m = mastery[TOPICS[n]]
    diff = "easy" if m < 0.40 else ("medium" if m < 0.75 else "hard")
    return n, diff, f"Weakest topic (mastery {m:.2f})"


def make_question(lecture, difficulty):
    used = {h["source"] for h in history}
    pool = [c for c in chunks
            if c["type"] == "video" and len(c["text"]) > 400
            and c["lecture"] == lecture and c["source"] not in used]
    random.shuffle(pool)
    for c in pool[:8]:
        prompt = f"""Using ONLY the lecture excerpt below, write ONE multiple-choice
question for a student. The question must be answerable from the excerpt.
Difficulty must be: {difficulty}.
Return JSON with keys: "question" (string), "options" (list of exactly 4 strings,
no letter prefixes), "answer" (index 0-3 of the correct option),
"explanation" (1-2 sentences), "difficulty" (string).

Excerpt:
{c['text'][:1800]}"""
        try:
            q = call_json(prompt)
            ok = (isinstance(q.get("options"), list) and len(q["options"]) == 4
                  and q.get("answer") in (0, 1, 2, 3))
            if not ok:
                continue
            if hist_vecs:
                qv = embed_text(q["question"])
                if float(np.max(np.array(hist_vecs) @ qv)) > SIM_LIMIT:
                    continue
            check = call_json(
                "Using ONLY the excerpt, choose the correct option. "
                'Return JSON {"answer": index 0-3}.\n\n'
                f"Excerpt:\n{c['text'][:1800]}\n\nQuestion: {q['question']}\n"
                f"Options: {q['options']}"
            )
            if check.get("answer") != q["answer"]:
                continue
        except Exception as e:
            print("quiz error:", str(e)[:150])
            time.sleep(3)
            continue
        q["chunk"] = c
        return q
    return None


class ChatIn(BaseModel):
    question: str
    lang: str = "en"


class AnswerIn(BaseModel):
    id: str
    choice: int


@app.get("/api/health")
def health():
    return {"ok": True, "chunks": len(chunks)}


@app.post("/api/chat")
def chat(body: ChatIn):
    question = body.question.strip()
    lang = "ur" if body.lang == "ur" else "en"
    if not question:
        raise HTTPException(400, "Empty question")
    hits = search(question)
    best = round(hits[0][1], 2)
    if hits[0][1] < MIN_SCORE:
        return {"answer": REFUSAL[lang], "refused": True, "best_score": best, "reason": "low_score", "sources": []}
    context = "\n\n".join(
        f"[{i}] ({c['source']})\n{c['text'][:2200]}" for i, (c, s) in enumerate(hits, 1)
    )
    language_rule = (
        "Write the explanation in Urdu (Urdu script). Keep technical terms such as "
        "perceptron, gradient, regression and the citation markers like [1] exactly as they are."
        if lang == "ur" else "Write the explanation in English."
    )
    prompt = f"""You are a tutor. Answer ONLY using the numbered excerpts below.
Explain clearly in 3-6 sentences. {language_rule}
After each claim, put the excerpt number in square brackets, like [1].
Use what the excerpts say, even if they cover only part of the question or describe the idea in different words (for example, the normal vector of a hyperplane describes the decision boundary of a perceptron). If they only partly answer it, answer the supported part and add one sentence saying what the excerpts do not cover. Reply exactly NOT_IN_MATERIAL only if the excerpts contain nothing relevant to the question.
Do not use outside knowledge.

Excerpts:
{context}

Question: {question}"""
    try:
        r = client.models.generate_content(model=MODEL, contents=prompt)
    except Exception as e:
        raise HTTPException(502, "AI service error (maybe quota): " + str(e)[:150])
    answer = (r.text or "").strip()
    if "NOT_IN_MATERIAL" in answer:
        return {"answer": REFUSAL[lang], "refused": True, "best_score": best, "reason": "model_declined", "sources": []}
    sources = [{"n": i, "label": c["source"], "type": c["type"],
                "score": round(s, 2), "url": link(c)}
               for i, (c, s) in enumerate(hits, 1)]
    return {"answer": answer, "refused": False, "best_score": best, "sources": sources}


@app.get("/api/quiz/next")
def quiz_next():
    lecture, difficulty, reason = choose_lecture()
    q = make_question(lecture, difficulty)
    if not q:
        raise HTTPException(503, "Could not make a verified question right now. Try again in a minute.")
    c = q["chunk"]
    order = list(range(4))
    random.shuffle(order)
    options = [q["options"][i] for i in order]
    qid = uuid.uuid4().hex[:8]
    PENDING[qid] = {
        "question": q["question"], "options": options,
        "correct": order.index(q["answer"]), "explanation": q["explanation"],
        "chunk": c, "difficulty": difficulty,
    }
    return {"id": qid, "topic": TOPICS[c["lecture"]], "difficulty": difficulty,
            "reason": reason, "question": q["question"], "options": options}


@app.post("/api/quiz/answer")
def quiz_answer(body: AnswerIn):
    p = PENDING.pop(body.id, None)
    if not p:
        raise HTTPException(404, "Question expired. Get a new one.")
    c = p["chunk"]
    is_right = body.choice == p["correct"]
    topic = TOPICS[c["lecture"]]
    history.append({"question": p["question"], "source": c["source"]})
    hist_vecs.append(embed_text(p["question"]))
    answers.append({
        "lecture": c["lecture"], "topic": topic, "difficulty": p["difficulty"],
        "correct": is_right, "source": c["source"],
        "question": p["question"],
        "chosen": p["options"][body.choice] if 0 <= body.choice < len(p["options"]) else None,
        "correct_text": p["options"][p["correct"]], "explanation": p["explanation"], "url": link(c),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save(HISTORY, history)
    save(ANSWERS, answers)
    return {"correct": is_right, "correct_index": p["correct"],
            "explanation": p["explanation"],
            "source": {"label": c["source"], "url": link(c)}}


@app.get("/api/mastery")
def mastery_api():
    m, counts, rights = state()
    topics = []
    for n, t in TOPICS.items():
        asked = counts.get(t, 0)
        score = round(m[t], 2) if t in m else None
        if asked == 0:
            status = "not tested"
        elif score < 0.40:
            status = "weak"
        elif score < 0.75:
            status = "ok"
        else:
            status = "strong"
        topics.append({"topic": t, "asked": asked, "right": rights.get(t, 0),
                       "mastery": score, "status": status})
    return {"topics": topics, "recent": answers[-10:][::-1], "total_answers": len(answers)}


REPORT_CACHE = {"n": -1, "mis": {}}


def _wrong_for(topic, limit=5):
    out = []
    for a in reversed(answers):
        if a["topic"] == topic and not a["correct"]:
            out.append({
                "question": a.get("question"), "chosen": a.get("chosen"),
                "correct_answer": a.get("correct_text"), "explanation": a.get("explanation"),
                "source": a["source"], "url": a.get("url") or f"{BASE}/slides/{a['lecture']}",
            })
        if len(out) >= limit:
            break
    return out


@app.get("/api/report")
def report_api(refresh: bool = False):
    m, counts, rights = state()
    topics = []
    for n, t in TOPICS.items():
        asked = counts.get(t, 0)
        score = round(m[t], 2) if t in m else None
        if asked == 0:
            status = "not tested"
        elif score < 0.40:
            status = "weak"
        elif score < 0.75:
            status = "ok"
        else:
            status = "strong"
        topics.append({"topic": t, "lecture": n, "asked": asked, "right": rights.get(t, 0),
                       "mastery": score, "status": status})
    weak = sorted([x for x in topics if x["status"] in ("weak", "ok")], key=lambda x: x["mastery"])
    for w in weak:
        w["wrong"] = _wrong_for(w["topic"])
        w["review_url"] = f"{BASE}/slides/{w['lecture']}"
    # Likely misconceptions: one model call, reused until a new answer arrives.
    need = [w for w in weak if any(x.get("chosen") for x in w["wrong"])]
    if need and (refresh or REPORT_CACHE["n"] != len(answers)):
        lines = []
        for w in need:
            lines.append("TOPIC: " + w["topic"])
            for x in w["wrong"]:
                if x.get("chosen"):
                    lines.append(f"- Question: {x['question']} | Student chose: {x['chosen']} | "
                                 f"Correct: {x['correct_answer']}")
        prompt = (
            "A student answered practice questions from a machine learning course. For each topic below the "
            "student's WRONG answers are listed. For each topic write ONE likely misconception in at most "
            "2 sentences, based only on these wrong answers, and word it as a likely cause (not a certainty). "
            "If there is not enough information, use an empty string. "
            "Return a JSON object that maps each topic name to its string.\n\n" + "\n".join(lines)
        )
        try:
            REPORT_CACHE["mis"] = call_json(prompt)
            REPORT_CACHE["n"] = len(answers)
        except Exception as e:
            print("report error:", str(e)[:150])
    mis = REPORT_CACHE["mis"] if isinstance(REPORT_CACHE["mis"], dict) else {}
    for w in weak:
        v = mis.get(w["topic"])
        w["likely_misconception"] = v if isinstance(v, str) and v.strip() else None
    return {"total_answers": len(answers), "overall_correct": sum(1 for a in answers if a["correct"]),
            "topics": topics, "weak": weak,
            "note": "Misconceptions are inferred by the language model from the wrong answers, so they are "
                    "marked likely. Mastery numbers come from hand-set tracing parameters."}


@app.get("/report")
def report_page():
    return FileResponse("report.html", media_type="text/html")


@app.get("/slides/{lecture}")
def slides(lecture: int):
    path = f"data/slides_0{lecture}.pdf"
    if lecture not in TOPICS or not os.path.exists(path):
        raise HTTPException(404, "Slides not found")
    return FileResponse(path, media_type="application/pdf")
