import json
import os
import sys

import numpy as np
from dotenv import load_dotenv
from fastembed import TextEmbedding
from google import genai

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.5-flash-lite"
MIN_SCORE = 0.30  # shuruati andaza, test se theek karenge
N_VIDEO = 4
N_SLIDES = 3

with open("data/chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)
emb = np.load("data/embeddings.npy")
emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
embedder = TextEmbedding("BAAI/bge-small-en-v1.5")

REFUSAL = "This is not covered in the course material (Lectures 1-5), so I can't answer it from the sources."


def search(question):
    q = np.array(list(embedder.query_embed(question))[0], dtype="float32")
    q = q / np.linalg.norm(q)
    scores = emb @ q
    order = scores.argsort()[::-1]
    video = [i for i in order if chunks[i]["type"] == "video"][:N_VIDEO]
    slides = [
        i for i in order
        if chunks[i]["type"] == "slide" and len(chunks[i]["text"]) >= 40
    ][:N_SLIDES]
    picked = sorted(video + slides, key=lambda i: -scores[i])
    return [(chunks[i], float(scores[i])) for i in picked]


def where(c):
    if c["type"] == "video":
        return c["url"]
    return f"open data/slides_0{c['lecture']}.pdf, page {c['slide']}"


def ask(question):
    hits = search(question)
    print(f"\n(best match score: {hits[0][1]:.2f})")
    if hits[0][1] < MIN_SCORE:
        print("\n" + REFUSAL)
        return
    context = "\n\n".join(
        f"[{i}] ({c['source']})\n{c['text'][:1500]}"
        for i, (c, s) in enumerate(hits, 1)
    )
    prompt = f"""You are a tutor. Answer ONLY using the numbered excerpts below.
Explain clearly in 3-6 sentences.
After each claim, put the excerpt number in square brackets, like [1].
If the excerpts do not contain the answer, reply exactly: NOT_IN_MATERIAL
Do not use outside knowledge.

Excerpts:
{context}

Question: {question}"""
    r = client.models.generate_content(model=MODEL, contents=prompt)
    answer = (r.text or "").strip()
    if "NOT_IN_MATERIAL" in answer:
        print("\n" + REFUSAL)
        return
    print("\n" + answer)
    print("\nSources:")
    for i, (c, s) in enumerate(hits, 1):
        print(f"[{i}] {c['source']}  (match {s:.2f})  ->  {where(c)}")


print("Tutor ready. Type a question (or 'quit').")
while True:
    q = input("\nYou: ").strip()
    if q.lower() in ("quit", "exit", ""):
        break
    try:
        ask(q)
    except Exception as e:
        print("Error:", e)