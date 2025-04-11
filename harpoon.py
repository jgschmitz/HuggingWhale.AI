# harpoon.py
from pymongo import MongoClient
from transformers import pipeline
import numpy as np

class Harpoon:
    def __init__(self, mongo_uri, db_name, collection_name, top_k=5):
        self.client = MongoClient(mongo_uri)
        self.collection = self.client[db_name][collection_name]
        self.intent_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        self.top_k = top_k

    def classify_intent(self, query):
        intents = ["troubleshooting", "how-to", "error", "specification", "general info"]
        result = self.intent_classifier(query, intents)
        return result['labels'][0]  # top intent

    def fetch_candidates(self, intent):
        """Basic filter. You can make this smarter by mapping intent -> Mongo filter."""
        return list(self.collection.find({"tags": intent}))  # assuming documents are tagged with topics

    def score_candidates(self, query, docs):
        """Very simple scoring — cosine similarity of text embedding could replace this."""
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer('all-MiniLM-L6-v2')
        query_embedding = model.encode(query, convert_to_tensor=True)
        doc_embeddings = model.encode([doc['text'] for doc in docs], convert_to_tensor=True)

        scores = util.pytorch_cos_sim(query_embedding, doc_embeddings)[0]
        scored_docs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, score in scored_docs[:self.top_k]]

    def sharpen_context(self, query):
        intent = self.classify_intent(query)
        raw_docs = self.fetch_candidates(intent)
        return self.score_candidates(query, raw_docs)

