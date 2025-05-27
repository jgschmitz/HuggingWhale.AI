from datasets import load_dataset
from voyageai import Client as VoyageClient
import numpy as np
from scipy.spatial.distance import cdist
import random

# ==== Config ====
api_key = "" #plug your voyageAI or any key here 
model_name = "voyage-2" #swap in or out any model 
max_pairs = 100

print("📦 Loading Quora Question Pairs...")
dataset = load_dataset("quora", split="train")

# Filter for only matching (duplicate) question pairs
positive_pairs = [
    (item["questions"]["text"][0], item["questions"]["text"][1])
    for item in dataset
    if item["is_duplicate"]
]

sampled = random.sample(positive_pairs, min(max_pairs, len(positive_pairs)))
query_texts = [q1 for q1, _ in sampled]
doc_texts = [q2 for _, q2 in sampled]

print(f"\n🔍 Preparing {len(sampled)} positive query-doc pairs...")

# ==== Embedding ====
def normalize(vectors):
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-8, None)

if not query_texts or not doc_texts:
    raise ValueError("🚨 No valid query-doc pairs were found!")

print(f"\n🧠 Embedding {len(query_texts)} query-doc pairs using model: {model_name}")
voyage = VoyageClient(api_key=api_key)

q_vecs = normalize(np.nan_to_num(voyage.embed(query_texts, model=model_name).embeddings))
d_vecs = normalize(np.nan_to_num(voyage.embed(doc_texts, model=model_name).embeddings))

# ==== Top-1 Retrieval Accuracy ====
sims = 1 - cdist(q_vecs, d_vecs, metric="cosine")
hits = sum(np.argmax(row) == i for i, row in enumerate(sims))
accuracy = hits / len(query_texts)

print(f"\n✅ Top-1 Retrieval Accuracy on Quora Pairs ({model_name}): {accuracy:.2%}")
