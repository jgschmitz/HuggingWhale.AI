<p align="center">
  <img src="hw-logo.png" width="260" alt="HuggingWhale Logo">
</p>

<h1 align="center">🤗🐋 HuggingWhale.AI</h1>

<p align="center"><em>AI That Hugs Your Data</em></p>

<hr>

<p align="center">
  <a href="https://www.buymeacoffee.com/jgschmitz" target="_blank">
    <img src="https://img.buymeacoffee.com/button-api/?text=☕+buy+me+a+coffee&emoji=☕&slug=jgschmitz&button_colour=FFDD00&font_colour=000000&font_family=Comic&outline_colour=000000&coffee_colour=ffffff" height="50" />
  </a>
</p>

</a> <br>
HuggingWhale.AI implements a modern Retrieval-Augmented Generation (RAG) pipeline purpose-built for unstructured document understanding and conversational querying. The system combines semantic chunking, vector embeddings, hybrid retrieval, and large language model (LLM) synthesis to deliver accurate and context-aware responses.

Drop your PDF / audio / messy doc → Get structured insights like it’s nothing. <br>
<br>
🤖 What is this? <br>
huggingwhale.ai is your all-in-one, zero-config, emoji-laden, AI wrapper playground that helps you pretend you're doing real machine learning.<br>
<Br>
We took all the hard stuff (RAG, chunking, embeddings, multi-agent orchestration)
and wrapped it in a giant whale hug. So now, you too can act like an AI savant with minimal effort. 🧠💅

🚀 Features
Automated Chunking: Utilizes recursive chunking strategies to preserve semantic coherence while respecting token limitations.

Flexible Embeddings: Supports embeddings via Voyage AI or OpenAI.

Hybrid Retrieval: Combines vector similarity search with keyword/category filtering for enhanced relevance.

LLM Integration: Generates grounded, explainable answers using OpenAI GPT-4.

User-Friendly Interface: Interact through a CLI or web-based interface for real-time recommendations and insights.​
🔐 Hug-First Privacy
No snooping. No telemetry. No weird terms of service.
Just warm, consensual AI processing.

🔧 Installation
```
git clone https://github.com/your-org/huggingwhale.ai.git
cd huggingwhale.ai
pip install -r requirements.txt
python app.py
```
```
pip install -r requirements.txt
python app.py
```

or for the sophisticated:

```
docker run --rm -it huggingwhale/ai:latest
🎛️ Configuration (optional, like pants in a Zoom call)
```
```
rag:
  chunk_size: auto-magical
  embed_model: whale-babbler-v2
agents:
  - name: Therapist
    tone: Gentle
  - name: SassyBot
    tone: Aggressively helpful
…but seriously, it just works™.
```

🧪 Example Use Case
```
curl -X POST -F "file=@your_messy_notes.pdf" http://localhost:8000/parse
Output:
{
  "summary": "Your notes were unhinged. Here's what we salvaged:",
  "insights": ["Start a cult?", "Buy GPU?", "Call mom."]
}
```

🤝 Contributing:
We welcome PRs, feature requests, or just good vibes in our issues.

If you write good code, we might even react with 🐳.

📝 License
MIT. Because your startup lawyer ghosted you and we’re chill.

💬 Final Thought
AI won’t replace you.
But huggingwhale.ai might make you look like you know what you're doing.
