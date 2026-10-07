import json
import sys

import numpy as np
from fastembed import TextEmbedding

sys.stdout.reconfigure(encoding="utf-8")

with open("data/chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)

texts = [c["text"][:2000] for c in chunks]

print("Loading model (first time downloads about 130 MB)...")
model = TextEmbedding("BAAI/bge-small-en-v1.5")

vectors = []
for i, v in enumerate(model.embed(texts, batch_size=32), 1):
    vectors.append(v)
    if i % 100 == 0:
        print(f"embedded {i} / {len(texts)}")

np.save("data/embeddings.npy", np.array(vectors, dtype="float32"))
print("DONE. Saved data/embeddings.npy", np.array(vectors).shape)