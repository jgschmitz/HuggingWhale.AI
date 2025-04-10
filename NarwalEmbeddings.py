import os
import pymongo
import warnings
from sentence_transformers import SentenceTransformer

# Suppress all warnings (including FutureWarnings)
warnings.simplefilter(action="ignore", category=FutureWarning)

# Suppress Transformers & PyTorch warnings via environment variables
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["PYTORCH_NO_ADVISORY_WARNINGS"] = "1"

# MongoDB connection
client = pymongo.MongoClient("mongodb+srv://jschmitz:slb2021@darkstar.tnhx6.mongodb.net/?retryWrites=true&w=majority")
db = client.vector_tests

# Load sentence transformer model
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Manually access the tokenizer and set clean_up_tokenization_spaces to False
if hasattr(model, "tokenizer"):
    model.tokenizer.clean_up_tokenization_spaces = False

# List of documents
docs = [
    "The students studied for their exams.",
    "Studying hard, the students prepared for their exams.",
    "The chef cooked a delicious meal.",
    "The chef cooked the chicken with the vegetables.",
    "Known for its power and aggression, Mike Tyson's boxing style was feared by many."
]

# Print sentences
print(docs)

# Insert documents into MongoDB
for doc in docs:
    doc_vector = model.encode(doc).tolist()
    result_doc = {
        'sentence': doc,
        'vectorEmbedding': doc_vector
    }
    result = db.vectors_demo_1.insert_one(result_doc)
    print(result)
