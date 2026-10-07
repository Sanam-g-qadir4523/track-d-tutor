import json
import os
import sys

from dotenv import load_dotenv
from google import genai
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

with open("data/chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)

vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
matrix = vec.fit_transform([c["text"] for c in chunks])

question = "What is a perceptron?"
scores = cosine_similarity(vec.transform([question]), matrix)[0]
top = scores.argsort()[::-1][:5]

print("=== TOP 5 SEARCH RESULTS ===")
for rank, i in enumerate(top, 1):
    c = chunks[i]
    print(f"\n[{rank}] score={scores[i]:.3f}  {c['source']}")
    print(c["text"][:300].replace("\n", " | "))

context = "\n\n".join(
    f"[{r}] ({chunks[i]['source']})\n{chunks[i]['text'][:1500]}"
    for r, i in enumerate(top, 1)
)
prompt = f"""You are a tutor. Answer ONLY using the numbered excerpts below.
After each claim, put the excerpt number in square brackets, like [1].
If the excerpts do not contain the answer, reply exactly: NOT_IN_MATERIAL
Do not use outside knowledge.

Excerpts:
{context}

Question: {question}"""

r = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)
print("\n=== GEMINI RAW ANSWER ===")
print(r.text)