import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

# Bayesian Knowledge Tracing: shuruati parameters (andaze, kisi data se fit nahi kiye)
P_INIT = 0.30   # shuru mein topic aane ka imkaan
P_LEARN = 0.15  # har sawal ke baad seekhne ka imkaan
P_GUESS = 0.25  # andaze se sahi jawab dene ka imkaan
P_SLIP = 0.10   # aata ho phir bhi galat jawab dene ka imkaan
WEAK = 0.40

TOPICS = {1: "Basics", 2: "Perceptrons", 3: "Features",
          4: "Logistic regression", 5: "Regression"}

if not os.path.exists("data/answers.json"):
    raise SystemExit("No answers yet. Run python quiz.py first.")
with open("data/answers.json", encoding="utf-8") as f:
    answers = json.load(f)


def update(p, correct):
    if correct:
        post = p * (1 - P_SLIP) / (p * (1 - P_SLIP) + (1 - p) * P_GUESS)
    else:
        post = p * P_SLIP / (p * P_SLIP + (1 - p) * (1 - P_GUESS))
    return post + (1 - post) * P_LEARN


mastery = {}
stats = {}
for a in answers:
    t = a["topic"]
    mastery.setdefault(t, P_INIT)
    stats.setdefault(t, [0, 0])
    mastery[t] = update(mastery[t], a["correct"])
    stats[t][0] += 1
    stats[t][1] += int(a["correct"])

print(f"{'Topic':<22}{'Asked':>6}{'Right':>6}{'Mastery':>9}  Status")
for t in TOPICS.values():
    if t in mastery:
        m = mastery[t]
        status = "WEAK - revise" if m < WEAK else ("OK" if m < 0.75 else "STRONG")
        print(f"{t:<22}{stats[t][0]:>6}{stats[t][1]:>6}{m:>9.2f}  {status}")
    else:
        print(f"{t:<22}{0:>6}{0:>6}{'-':>9}  not tested yet")

with open("data/mastery.json", "w", encoding="utf-8") as f:
    json.dump({t: round(m, 3) for t, m in mastery.items()}, f, indent=2)
print("\nSaved data/mastery.json")