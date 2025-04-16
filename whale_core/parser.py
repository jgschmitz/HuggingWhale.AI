import os
import PyPDF2
import whisper
from pydub import AudioSegment
from sentence_transformers import SentenceTransformer

import warnings
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="`clean_up_tokenization_spaces` was not set.*"
)
model = SentenceTransformer('all-MiniLM-L6-v2')

def parse_pdf(filepath):
    text = ""
    with open(filepath, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

def parse_audio(filepath):
    model = whisper.load_model("base")
    result = model.transcribe(filepath)
    return result['text']

def parse_text(filepath):
    with open(filepath, 'r') as f:
        return f.read()

def parse_file(filepath):
    if filepath.endswith('.pdf'):
        return parse_pdf(filepath)
    elif filepath.endswith(('.mp3', '.wav', '.m4a')):
        return parse_audio(filepath)
    elif filepath.endswith('.txt'):
        return parse_text(filepath)
    else:
        raise ValueError(f"Unsupported file type: {filepath}")

def chunk_text(text, chunk_size=300):
    words = text.split()
    return [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def chunk_and_embed(text):
    chunks = chunk_text(text)
    embeddings = model.encode(chunks).tolist()
    return list(zip(chunks, embeddings))
