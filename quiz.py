import json
import os
import random
import sys
import time

import numpy as np
from dotenv import load_dotenv
from fastembed import TextEmbedding
from google import genai
from google.genai import types

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
embedder = TextEmbedding("BAAI/bge-small-en-v1.5")

MODEL = "gemini-3.5-flash-lite"
TOPICS = {1: "Basics", 2: "Perceptrons", 3: "Features",
          4: "Logistic regression", 5: "Regression"}
HISTORY = "data/quiz_history.json"
ANSWERS = "data/answers.json"
N_QUESTIONS = 3
SIM_LIMIT = 0.88  # andazi hadd: isse zyada milta sawal repeat samjha jata hai

# BKT ke andazi parameters (learner.py wale hi)
P_INIT, P_LEARN, P_GUESS, P_SLIP = 0.30, 0.15, 0.25, 0.10


def load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def call_json(prompt):
    r = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(r.text)


def embed(text):
    v = np.array(list(embedder.embed([text]))[0], dtype="float32")
    return v / np.linalg.norm(v)


def bkt_update(p, correct):
    if correct:
        post = p * (1 - P_SLIP) / (p * (1 - P_SLIP) + (1 - p) * P_GUESS)
    else:
        post = p * P_SLIP / (p * P_SLIP + (1 - p) * (1 - P_GUESS))
    return post + (1 - post) * P_LEARN


def state():
    mastery, counts = {}, {}
    for a in answers:
        t = a["topic"]
        mastery.setdefault(t, P_INIT)
        counts[t] = counts.get(t, 0) + 1
        mastery[t] = bkt_update(mastery[t], a["correct"])
    return mastery, counts


def choose_lecture():
    mastery, counts = state()
    untested = [n for n, t in TOPICS.items() if counts.get(t, 0) == 0]
    if untested:
        n = random.choice(untested)
        return n, "easy", "diagnostic (topic not tested yet)"
    n = min(TOPICS, key=lambda k: mastery[TOPICS[k]])
    m = mastery[TOPICS[n]]
    diff = "easy" if m < 0.40 else ("medium" if m < 0.75 else "hard")
    return n, diff, f"weakest topic (mastery {m:.2f})"


with open("data/chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)
history = load(HISTORY)
answers = load(ANSWERS)
hist_vecs = [embed(h["question"]) for h in history]


def make_question(lecture, difficulty):
    used = {h["source"] for h in history}
    pool = [
        c for c in chunks
        if c["type"] == "video" and len(c["text"]) > 400
        and c["lecture"] == lecture and c["source"] not in used
    ]
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
                qv = embed(q["question"])
                if float(np.max(np.array(hist_vecs) @ qv)) > SIM_LIMIT:
                    print("(one question dropped: too similar to an earlier one)")
                    continue
            check = call_json(
                "Using ONLY the excerpt, choose the correct option. "
                'Return JSON {"answer": index 0-3}.\n\n'
                f"Excerpt:\n{c['text'][:1800]}\n\nQuestion: {q['question']}\n"
                f"Options: {q['options']}"
            )
            if check.get("answer") != q["answer"]:
                print("(one question dropped: verification disagreed)")
                continue
        except Exception as e:
            print("Error:", str(e)[:150])
            time.sleep(5)
            continue
        q["chunk"] = c
        return q
    return None


print("Topics: " + ", ".join(f"{k}={v}" for k, v in TOPICS.items()))
choice = input("Lecture number (1-5), or 0 for ADAPTIVE (recommended): ").strip()
fixed = int(choice) if choice in ("1", "2", "3", "4", "5") else 0

score = 0
asked = 0
for n in range(1, N_QUESTIONS + 1):
    if fixed:
        lecture, difficulty, reason = fixed, "medium", "fixed lecture"
    else:
        lecture, difficulty, reason = choose_lecture()
    print(f"\n[Adaptive] {TOPICS[lecture]} - {reason}")
    q = make_question(lecture, difficulty)
    if not q:
        print("Could not make a verified question right now. Try again later.")
        break
    c = q["chunk"]
    correct = q["answer"]
    order = list(range(4))
    random.shuffle(order)
    topic = TOPICS[c["lecture"]]
    print(f"Q{n} [{topic} | {difficulty}]")
    print(q["question"])
    for letter, idx in zip("ABCD", order):
        print(f"  {letter}) {q['options'][idx]}")
    pick = ""
    while pick not in ("A", "B", "C", "D"):
        pick = input("Your answer (A/B/C/D): ").strip().upper()
    chosen = order["ABCD".index(pick)]
    is_right = chosen == correct
    asked += 1
    score += int(is_right)
    print("Correct!" if is_right else
          f"Not quite. Correct answer: {q['options'][correct]}")
    print("Why:", q["explanation"])
    print("Source:", c["source"], "->", c["url"])
    history.append({"question": q["question"], "source": c["source"]})
    hist_vecs.append(embed(q["question"]))
    answers.append({
        "lecture": c["lecture"], "topic": topic,
        "difficulty": difficulty, "correct": is_right,
        "source": c["source"], "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save(HISTORY, history)
    save(ANSWERS, answers)

print(f"\nScore: {score} / {asked}")