from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')
client = MongoClient()
db = client['huggingwhale']
collection = db['docs']

def chunk_text(text, chunk_size=300):
    words = text.split()
    return [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def embed_chunks(chunks):
    return model.encode(chunks).tolist()

def store_embeddings(chunks, embeddings):
    docs = [
        {"chunk": chunk, "embedding": emb}
        for chunk, emb in zip(chunks, embeddings)
    ]
    collection.insert_many(docs)

def query_rag(question, top_k=3):
    question_vec = model.encode([question])[0]
    results = collection.aggregate([
        {
            "$vectorSearch": {
                "index": "default",
                "path": "embedding",
                "queryVector": question_vec,
                "numCandidates": 100,
                "limit": top_k
            }
        }
    ])
    return [doc['chunk'] for doc in results]
