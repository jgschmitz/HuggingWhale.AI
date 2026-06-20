import os

import voyageai
from pymongo import MongoClient

VOYAGE_MODEL = os.getenv("VOYAGE_EMBED_MODEL", "voyage-3")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "huggingwhale")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION", "docs")
VECTOR_INDEX = os.getenv("MONGO_VECTOR_INDEX", "default")


def _voyage_key():
    key = os.getenv("VOYAGE_API_KEY")
    if not key:
        try:
            import streamlit as st

            key = st.secrets.get("VOYAGE_API_KEY")
        except Exception:
            key = None
    if not key:
        raise ValueError("No Voyage API key found. Set VOYAGE_API_KEY.")
    return key


_voyage = None
_collection = None


def _voyage_client():
    global _voyage
    if _voyage is None:
        _voyage = voyageai.Client(api_key=_voyage_key())
    return _voyage


def get_collection():
    global _collection
    if _collection is None:
        client = MongoClient(MONGO_URI)
        _collection = client[DB_NAME][COLLECTION_NAME]
    return _collection


def chunk_text(text, chunk_size=300):
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]


def embed_chunks(chunks, input_type="document"):
    result = _voyage_client().embed(chunks, model=VOYAGE_MODEL, input_type=input_type)
    return result.embeddings


def store_embeddings(chunks, embeddings):
    docs = [{"chunk": chunk, "embedding": emb} for chunk, emb in zip(chunks, embeddings)]
    if docs:
        get_collection().insert_many(docs)


def query_rag(question, top_k=3):
    question_vec = embed_chunks([question], input_type="query")[0]
    results = get_collection().aggregate([
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX,
                "path": "embedding",
                "queryVector": question_vec,
                "numCandidates": 100,
                "limit": top_k,
            }
        }
    ])
    return [doc["chunk"] for doc in results]
