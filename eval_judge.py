"""
eval_judge.py - answer-quality evaluation for Course Companion (Track D)

Uses the SAME search() and MIN_SCORE as server.py and the SAME test set as eval.py.

Part A (0 Gemini calls): context precision and context recall (proxy metrics)
Part B (about 20 Gemini calls): faithfulness and answer relevancy by an LLM judge.
   This is an "LLM-as-judge", NOT RAGAS. The judge is the same model family that
   writes the answers, so scores may be optimistic. State both in the report.

Run from the project folder:
    python eval_judge.py --retrieval   # Part A only, no Gemini calls
    python eval_judge.py               # Part A + Part B
Output: data/eval_judge_results.json   (does NOT overwrite eval_results.json)
"""
import json
import os
import re
import sys
import time

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

from server import MIN_SCORE, search  # noqa: E402  (same retrieval as the app)

# Same test set as eval.py: (question, expected lecture, keyword)
IN_COURSE = [
    ("What is a perceptron?", 2, "perceptron"),
    ("How does the perceptron algorithm learn from its mistakes?", 2, "perceptron"),
    ("What does theta represent geometrically for a hyperplane?", 2, "normal"),
    ("What is linear regression?", 5, "regression"),
    ("Why can a closed-form solution be too costly for linear regression?", 5, "invers"),
    ("What does regularization do to the objective?", 5, "penalty"),
    ("How do you choose the regularization strength lambda?", 4, "cross"),
    ("What is a hypothesis in machine learning?", 1, "hypothesis"),
    ("Why is saying every newborn had a seizure a poor hypothesis?", 1, "seizure"),
    ("How many labels does the heart disease prediction problem have?", 3, "heart"),
    ("What is logistic regression?", 4, "logistic"),
    ("What happens to the objective if lambda is negative?", 5, "negative"),
]

N_JUDGED = 10                                   # questions sent to the LLM judge (2 calls each)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
OUT = "data/eval_judge_results.json"


def load_env():
    if os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"'))


# ------------------------------------------------------------------ Part A
def part_a():
    rows = []
    for q, lec, kw in IN_COURSE:
        hits = search(q)                               # list of (chunk, score)
        from_lecture = [c["lecture"] == lec for c, _ in hits]
        has_kw = [kw in c["text"].lower() for c, _ in hits]
        rows.append({
            "question": q,
            "n_retrieved": len(hits),
            # precision: share of retrieved passages that come from the expected lecture
            "precision_lecture": sum(from_lecture) / len(hits),
            # precision (strict): share that are from the expected lecture AND contain the keyword
            "precision_strict": sum(a and b for a, b in zip(from_lecture, has_kw)) / len(hits),
            # recall: 1 if at least one retrieved passage is from the expected lecture and has the keyword
            "recall_hit": 1.0 if any(a and b for a, b in zip(from_lecture, has_kw)) else 0.0,
        })
    return {
        "context_precision_lecture": round(float(np.mean([r["precision_lecture"] for r in rows])), 3),
        "context_precision_strict": round(float(np.mean([r["precision_strict"] for r in rows])), 3),
        "context_recall_hit": round(float(np.mean([r["recall_hit"] for r in rows])), 3),
        "note": "Proxy metrics (lecture number + keyword), not RAGAS. One expected lecture and one keyword per question.",
        "per_question": rows,
    }


# ------------------------------------------------------------------ Part B
_client = None


def gemini(prompt, retries=4):
    """Supports the new `google-genai` package and falls back to `google-generativeai`."""
    global _client
    key = os.environ["GEMINI_API_KEY"]
    for attempt in range(retries):
        try:
            try:
                from google import genai
                if _client is None:
                    _client = genai.Client(api_key=key)
                return _client.models.generate_content(model=GEMINI_MODEL, contents=prompt).text
            except ImportError:
                import google.generativeai as old
                old.configure(api_key=key)
                return old.GenerativeModel(GEMINI_MODEL).generate_content(prompt).text
        except Exception as e:
            wait = 8 * (attempt + 1)
            print(f"   Gemini error ({str(e)[:90]}); retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError("Gemini failed after retries")


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


# TODO (optional): replace this prompt with the exact grounded-answer prompt from server.py
# so the evaluation measures the real system. Keep the {ctx} and {q} placeholders.
ANSWER_PROMPT = (
    "You are a course tutor. Answer ONLY from the numbered excerpts below. "
    "Cite excerpt numbers like [1]. If the excerpts do not contain the answer, "
    "reply exactly NOT_IN_MATERIAL.\n\nEXCERPTS:\n{ctx}\n\nQUESTION: {q}\n\nANSWER:"
)

JUDGE_PROMPT = """You are a strict evaluator. Return ONLY JSON, no other text.

QUESTION: {q}

CONTEXT (the only allowed source):
{ctx}

ANSWER TO EVALUATE:
{answer}

Task 1 (faithfulness): split the answer into separate factual claims. For each claim say whether it is
directly supported by the CONTEXT (true) or not (false). Ignore citation markers like [1].
Task 2 (relevancy): rate 1 to 5 how directly and completely the answer addresses the QUESTION
(5 = fully and directly, 1 = off-topic or evasive).

JSON format:
{{"claims":[{{"claim":"...","supported":true}}],"relevancy":4,"relevancy_reason":"one short sentence"}}"""


def part_b():
    rows, faith, rel = [], [], []
    todo = IN_COURSE[:N_JUDGED]
    for n, (q, lec, kw) in enumerate(todo, 1):
        print(f"[{n}/{len(todo)}] {q}")
        hits = search(q)
        ctx = "\n\n".join(f"[{i+1}] {c['text']}" for i, (c, _) in enumerate(hits))
        answer = gemini(ANSWER_PROMPT.format(ctx=ctx, q=q)).strip()
        time.sleep(2)
        if answer.startswith("NOT_IN_MATERIAL"):
            rows.append({"question": q, "answer": answer,
                         "note": "model refused an in-course question"})
            continue
        j = parse_json(gemini(JUDGE_PROMPT.format(q=q, ctx=ctx, answer=answer)))
        claims = j.get("claims", [])
        f = (sum(1 for c in claims if c.get("supported")) / len(claims)) if claims else None
        r = (j.get("relevancy", 1) - 1) / 4          # 1..5 -> 0..1
        if f is not None:
            faith.append(f)
        rel.append(r)
        rows.append({"question": q, "answer": answer, "faithfulness": f,
                     "relevancy_1to5": j.get("relevancy"), "relevancy_reason": j.get("relevancy_reason"),
                     "unsupported_claims": [c["claim"] for c in claims if not c.get("supported")]})
        time.sleep(2)
    return {
        "judge": f"LLM-as-judge ({GEMINI_MODEL}). Same model family wrote the answers, so scores may be optimistic.",
        "n_questions": len(todo),
        "n_scored": len(rel),
        "faithfulness_mean": round(float(np.mean(faith)), 3) if faith else None,
        "answer_relevancy_mean_0to1": round(float(np.mean(rel)), 3) if rel else None,
        "per_question": rows,
    }


def main():
    load_env()
    out = {"min_score": MIN_SCORE, "retrieval": part_a()}
    r = out["retrieval"]
    print("\nPART A (no Gemini calls)")
    print(f"  context precision (lecture):  {r['context_precision_lecture']}")
    print(f"  context precision (strict):   {r['context_precision_strict']}")
    print(f"  context recall (hit):         {r['context_recall_hit']}")
    if "--retrieval" not in sys.argv:
        out["generation"] = part_b()
        g = out["generation"]
        print("\nPART B (LLM judge)")
        print(f"  faithfulness mean:     {g['faithfulness_mean']}")
        print(f"  answer relevancy mean: {g['answer_relevancy_mean_0to1']}  (0 to 1)")
        weak = [x for x in g["per_question"] if x.get("unsupported_claims")]
        print(f"  answers with unsupported claims: {len(weak)} of {g['n_scored']}")
    os.makedirs("data", exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
