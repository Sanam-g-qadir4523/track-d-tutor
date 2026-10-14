"""Simulated-student check of the adaptive policy.

This does NOT use real questions or the language model. It simulates students whose
true knowledge per topic is known to the simulation, and compares two ways of choosing
the next topic over several sessions:
  adaptive : untested topics first, then the topic with the lowest estimated mastery
             (the same rule the quiz uses), with mastery estimated by the same
             Bayesian knowledge tracing as the app.
  random   : a random topic each time.

Assumptions (all chosen by hand, not measured from real students):
  - a student answers correctly with probability k*(1-slip) + (1-k)*guess
  - after each question the student learns: k += LEARN_GAIN * (1 - k)

Run:  python sim.py
"""
import random

P_INIT, P_LEARN, P_GUESS, P_SLIP = 0.30, 0.15, 0.25, 0.10  # same values as the app
LEARN_GAIN = 0.08
TOPICS = 5
SESSIONS, PER_SESSION = 5, 6
STUDENTS_PER_PROFILE = 300
SEED = 0


def bkt_update(p, correct):
    if correct:
        post = p * (1 - P_SLIP) / (p * (1 - P_SLIP) + (1 - p) * P_GUESS)
    else:
        post = p * P_SLIP / (p * P_SLIP + (1 - p) * (1 - P_GUESS))
    return post + (1 - post) * P_LEARN


def make_student(profile, rng):
    if profile == "beginner":
        return [min(0.9, max(0.02, rng.gauss(0.2, 0.08))) for _ in range(TOPICS)]
    if profile == "mixed":
        return [rng.uniform(0.1, 0.8) for _ in range(TOPICS)]
    return [min(0.95, max(0.4, rng.gauss(0.65, 0.1))) for _ in range(TOPICS)]  # advanced


def run(policy, knowledge, rng):
    k = list(knowledge)
    est = [None] * TOPICS
    asked = [0] * TOPICS
    repeats = 0
    for _ in range(SESSIONS * PER_SESSION):
        untested = [t for t in range(TOPICS) if asked[t] == 0]
        if policy == "adaptive":
            if untested:
                t = rng.choice(untested)
            else:
                t = min(range(TOPICS), key=lambda i: est[i])
        else:
            t = rng.randrange(TOPICS)
        p_correct = k[t] * (1 - P_SLIP) + (1 - k[t]) * P_GUESS
        correct = rng.random() < p_correct
        est[t] = bkt_update(est[t] if est[t] is not None else P_INIT, correct)
        asked[t] += 1
        k[t] += LEARN_GAIN * (1 - k[t])
    err = sum(abs((est[t] if est[t] is not None else P_INIT) - k[t]) for t in range(TOPICS)) / TOPICS
    return k, err


def main():
    print("Simulated students: %d per profile, %d sessions of %d questions (%d questions each)"
          % (STUDENTS_PER_PROFILE, SESSIONS, PER_SESSION, SESSIONS * PER_SESSION))
    print("Learning gain per question (assumed): %.2f\n" % LEARN_GAIN)
    header = "%-10s %-9s %-13s %-17s %s" % ("profile", "policy", "mean gain", "gain on weakest", "tracking error")
    print(header)
    results = {}
    for profile in ("beginner", "mixed", "advanced"):
        for policy in ("adaptive", "random"):
            rng = random.Random(SEED)
            gains, weak_gains, errs = [], [], []
            for _ in range(STUDENTS_PER_PROFILE):
                start = make_student(profile, rng)
                final, err = run(policy, start, rng)
                gains.append(sum(final) / TOPICS - sum(start) / TOPICS)
                w = min(range(TOPICS), key=lambda i: start[i])
                weak_gains.append(final[w] - start[w])
                errs.append(err)
            n = len(gains)
            results[(profile, policy)] = (sum(gains) / n, sum(weak_gains) / n, sum(errs) / n)
            g, wg, e = results[(profile, policy)]
            print("%-10s %-9s %-13.3f %-17.3f %.3f" % (profile, policy, g, wg, e))
        print()
    print("mean gain       = average rise in true knowledge across the 5 topics (0 to 1 scale)")
    print("gain on weakest = rise on the topic the student started weakest in")
    print("tracking error  = average gap between the model's mastery estimate and true knowledge")
    print("\nQuestion repetition: every question comes from a different source passage, so repeats of the")
    print("same passage are 0 by construction. Near-duplicate wording is checked in the app, not here.")


if __name__ == "__main__":
    main()
