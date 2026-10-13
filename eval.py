"""Retrieval and refusal evaluation for the Track D tutor.

Runs without any Gemini calls, so it uses no API quota.
Metrics:
  1. Retrieval hit rate: do the returned passages include one from the expected
     lecture that contains the expected keyword?
  2. Top-1 lecture rate: is the single best passage from the expected lecture?
  3. Refusal: for off-topic questions, is the best match score below MIN_SCORE?
  4. A threshold sweep, so the refusal threshold is chosen from data.

Run:  python eval.py
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from server import MIN_SCORE, search  # noqa: E402

# (question, expected lecture, keyword that should appear in a returned passage)
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

OFF_TOPIC = [
    "Who won the cricket world cup?",
    "How do I bake a chocolate cake?",
    "Who is the president of France?",
    "What is the capital of Japan?",
    "Who is the best football player in the world?",
    "How do you say hello in French?",
    "What is the current price of Apple stock?",
    "What will the weather be like in Karachi tomorrow?",
]

rows = []
for q, lec, kw in IN_COURSE:
    hits = search(q)
    best = hits[0][1]
    hit = any(c["lecture"] == lec and kw in c["text"].lower() for c, s in hits)
    top1 = hits[0][0]["lecture"] == lec
    rows.append({"question": q, "expected_lecture": lec, "keyword": kw,
                 "best_score": round(best, 3), "hit": hit, "top1_lecture": top1,
                 "top1_source": hits[0][0]["source"]})

off_rows = []
for q in OFF_TOPIC:
    hits = search(q)
    off_rows.append({"question": q, "best_score": round(hits[0][1], 3),
                     "top1_source": hits[0][0]["source"]})

print("\nIN-COURSE QUESTIONS")
print(f"{'hit':<5}{'top1':<6}{'score':<8}question")
for r in rows:
    print(f"{'yes' if r['hit'] else 'NO':<5}{'yes' if r['top1_lecture'] else 'no':<6}"
          f"{r['best_score']:<8}{r['question']}")

print("\nOFF-TOPIC QUESTIONS")
print(f"{'score':<8}question")
for r in off_rows:
    print(f"{r['best_score']:<8}{r['question']}")

n = len(rows)
hit_rate = sum(r["hit"] for r in rows) / n
top1_rate = sum(r["top1_lecture"] for r in rows) / n
refused = sum(r["best_score"] < MIN_SCORE for r in off_rows) / len(off_rows)
accepted = sum(r["best_score"] >= MIN_SCORE for r in rows) / n

print("\nRESULTS AT THE CURRENT THRESHOLD (MIN_SCORE = %.2f)" % MIN_SCORE)
print(f"Retrieval hit rate (expected lecture and keyword): {hit_rate:.0%}  ({sum(r['hit'] for r in rows)}/{n})")
print(f"Top-1 passage from the expected lecture:           {top1_rate:.0%}")
print(f"In-course questions allowed through:               {accepted:.0%}")
print(f"Off-topic questions refused by the score check:    {refused:.0%}  ({sum(r['best_score'] < MIN_SCORE for r in off_rows)}/{len(off_rows)})")

print("\nTHRESHOLD SWEEP (higher threshold refuses more, but may block real questions)")
print(f"{'threshold':<11}{'in-course allowed':<20}{'off-topic refused'}")
sweep = []
for t in (0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70):
    a = sum(r["best_score"] >= t for r in rows) / n
    f = sum(r["best_score"] < t for r in off_rows) / len(off_rows)
    sweep.append({"threshold": t, "in_course_allowed": round(a, 3), "off_topic_refused": round(f, 3)})
    print(f"{t:<11.2f}{a:<20.0%}{f:.0%}")

with open("data/eval_results.json", "w", encoding="utf-8") as f:
    json.dump({"min_score": MIN_SCORE, "hit_rate": hit_rate, "top1_rate": top1_rate,
               "off_topic_refused": refused, "in_course_allowed": accepted,
               "in_course": rows, "off_topic": off_rows, "sweep": sweep},
              f, ensure_ascii=False, indent=2)
print("\nSaved data/eval_results.json")
