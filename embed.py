import json
import os
import sys
import time

import numpy as np
from dotenv import load_dotenv
from google import genai

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

with open("data/chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)

texts = [c["text"][:2000] for c in chunks]
PARTIAL = "data/embeddings_partial.npy"
BATCH = 50

vectors = []
if os.path.exists(PARTIAL):
    vectors = np.load(PARTIAL).tolist()
    print(f"Resuming from {len(vectors)} / {len(texts)}")

while len(vectors) < len(texts):
    start = len(vectors)
    batch = texts[start:start + BATCH]
    done = False
    for attempt in range(5):
        try:
            r = client.models.embed_content(
                model="gemini-embedding-001",
                contents=batch,
            )
            vectors.extend([e.values for e in r.embeddings])
            done = True
            break
        except Exception as e:
            print("limit/error, waiting 65 sec...", str(e)[:80])
            time.sleep(65)
    if not done:
        print(f"Stopped at {len(vectors)} / {len(texts)}. Progress is saved.")
        print("Run 'python embed.py' again after a few minutes.")
        raise SystemExit
    np.save(PARTIAL, np.array(vectors, dtype="float32"))
    print(f"embedded {len(vectors)} / {len(texts)}")
    time.sleep(3)

np.save("data/embeddings.npy", np.array(vectors, dtype="float32"))
print("DONE. Saved data/embeddings.npy")