# NarwalTrainer.py
import os
from pymongo import MongoClient
from datasets import Dataset
from unsloth import FastTrainer
from transformers import AutoTokenizer

# --- CONFIG ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "narwhal"
COLLECTION_NAME = "chunks"
MODEL_NAME = "unsloth/llama-3-8b-Instruct"  # or any compatible model

# --- 1. Connect to MongoDB ---
client = MongoClient(MONGO_URI)
collection = client[DB_NAME][COLLECTION_NAME]

# --- 2. Pull training data ---
# Expecting: { "input": "some chunked text", "output": "expected response" }
documents = list(collection.find({"input": {"$exists": True}, "output": {"$exists": True}}))

# --- 3. Convert to Hugging Face dataset ---
train_data = [{"text": f"### Input:\n{doc['input']}\n\n### Output:\n{doc['output']}"} for doc in documents]
dataset = Dataset.from_list(train_data)

# --- 4. Tokenizer and trainer ---
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

trainer = FastTrainer(
    model=MODEL_NAME,
    tokenizer=tokenizer,
    dataset=dataset,
    output_dir="./narwal_checkpoints",
    batch_size=4,
    fp16=True,
    epochs=3,
)

# --- 5. Go time ---
trainer.train()

print("✅ Narwhal fine-tuning complete! Checkpoints saved to ./narwal_checkpoints")
