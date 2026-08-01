# 🐳 HuggingWhale.AI — Tech Stack

> Drop a chaotic file. Get persona analysis, semantic search, and an autonomous agent that shows its work.

**Last verified against source:** 2026-08-01

---

## At a Glance

| Layer | Tech | Entry point |
|---|---|---|
| Ingestion | `pypdf` (PyPDF2 fallback), Whisper (optional) | `whale_core/parser.py` |
| Chunking | Word-window splitter (300 words) | `whale_core/rag.py` |
| Embeddings | Voyage AI (`voyage-3`) | `whale_core/rag.py` |
| Vector store | MongoDB Atlas `$vectorSearch` | `whale_core/rag.py` |
| Reasoning | Anthropic Claude + native tool use | `whale_core/react_agent.py` |
| Persona agents | OpenAI GPT-4 + YAML configs | `whale_core/agents.py` |
| UI | Gradio (docs + agent), Streamlit (chat) | `huggingparser.py`, `hugginglit.py` |

---

## 📝 1. Document Parsing

| Capability | Tech | Notes |
|---|---|---|
| PDF ingestion | `pypdf`, falls back to `PyPDF2` | Page-by-page text extraction |
| Text / Markdown | stdlib | `.txt`, `.md`, UTF-8 with replacement on bad bytes |
| Audio transcription | OpenAI Whisper (`base`) | Lazy-imported; raises a clear error if `ffmpeg` is missing |

`parse_file()` dispatches on extension and rejects anything else with an explicit
`ValueError`, so unsupported formats fail loudly instead of silently returning junk.

## ✂️ 2. Chunking

Chunking is a **300-word sliding window** implemented in `rag.chunk_text()` — plain
`text.split()`, no LangChain dependency. `parser.chunk_text()` is a thin delegate kept
for backwards compatibility.

`parser.chunk_and_embed(text, store=True)` chunks, embeds, and optionally persists in
one call. It swallows embedding failures and returns `[]`, which lets the UI keep
working when Voyage or MongoDB aren't configured.

> **Why it matters:** the app degrades gracefully. No API keys means no vector search,
> not a crash.

## 🧠 3. Embeddings

| Capability | Tech | Notes |
|---|---|---|
| Vector embeddings | Voyage AI `voyage-3` | Override via `VOYAGE_EMBED_MODEL` |
| Input-type awareness | `input_type="document"` / `"query"` | Voyage optimizes each side of the pair separately |
| Client caching | Module-level singleton | One client per process |
| Key resolution | env var → `st.secrets` | Works in both CLI and Streamlit contexts |

## 🔍 4. Retrieval

`rag.query_rag()` embeds the question, then runs a MongoDB `$vectorSearch` aggregation:

```python
{
    "$vectorSearch": {
        "index": VECTOR_INDEX,
        "path": "embedding",
        "queryVector": question_vec,
        "numCandidates": 100,
        "limit": top_k,
    }
}
```

Everything is env-configurable: `MONGO_URI`, `MONGO_DB`, `MONGO_COLLECTION`,
`MONGO_VECTOR_INDEX`. The connection pings on first use with a 5s timeout, so a bad URI
surfaces immediately rather than hanging.

## 🤖 5. The ReAct Agent

`react_agent.run()` is a genuine reason → act → observe loop over Claude's native tool
API (default `claude-sonnet-4-5`, max 6 steps). Every thought, action, and observation
is appended to a `trace` list that the UI renders — the reasoning is the product, not a
side effect.

**Tools available to the agent** (`whale_core/tools.py`):

| Tool | Purpose |
|---|---|
| `rag_search` | Semantic vector search over the indexed corpus |
| `document_lookup` | Exact keyword search with ±150 chars of context in the loaded doc |
| `calculator` | Arithmetic via a whitelisted AST evaluator — no `eval()` |

The calculator walks the AST and only permits `+ - * / ** %` and unary sign. Anything
else raises. That's the safe way to do this.

## 🎭 6. Persona Agents

`agents/config.yaml` defines four personas — **SummaryAgent**, **KeyPointAgent**,
**CritiqueAgent**, **RewriteAgent** — each a `persona` (system message) plus
`instructions`. `run_agents_on_text()` fans them out over OpenAI (default `gpt-4`,
first 4000 chars of the document) and returns a name → response map. Per-agent
exceptions are caught so one failure doesn't kill the batch.

Adding a persona is a YAML edit. No code change.

## 🖥️ 7. Interfaces

**`huggingparser.py` — Gradio, two tabs**
- *Persona Agents*: upload a PDF/text file, get all four persona responses; indexes to the vector store in the background and tells you if indexing was skipped.
- *ReAct Agent*: ask a question, get the answer plus the full reasoning trace.

**`hugginglit.py` — Streamlit**
A prompt box with an OpenAI / Voyage toggle. Straight passthrough, no RAG.

**`voyageHarness.py` — Benchmark**
Measures top-1 retrieval accuracy for the current Voyage model against 100 sampled
positive pairs from the Quora Question Pairs dataset. Useful for justifying a model
change with a number instead of a vibe.

## 🔐 8. Config

All secrets resolve **env var first, `.streamlit/secrets.toml` second**:

| Variable | Default |
|---|---|
| `VOYAGE_API_KEY` | *required for RAG* |
| `ANTHROPIC_API_KEY` | *required for the ReAct agent* |
| `OPENAI_API_KEY` | *required for persona agents* |
| `VOYAGE_EMBED_MODEL` | `voyage-3` |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5` |
| `OPENAI_MODEL` | `gpt-4` (personas) / `gpt-3.5-turbo` (chat) |
| `MONGO_URI` | `mongodb://localhost:27017` |
| `MONGO_DB` | `huggingwhale` |
| `MONGO_COLLECTION` | `docs` |
| `MONGO_VECTOR_INDEX` | `default` |

## ✅ 9. Tests

`tests/test_parser.py` and `tests/test_tools.py` cover parsing and the agent tools.

```bash
pytest tests/
```

---

## 🌊 Flow

```
              ┌─────────────────┐
  PDF / TXT ──▶  parse_file()   │
  MP3 / WAV   └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │  chunk_text()   │  300-word windows
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │  Voyage embed   │  input_type="document"
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ MongoDB Atlas   │  chunk + embedding
              └────────┬────────┘
                       │
   User question ──────┤
                       ▼
              ┌─────────────────┐
              │  ReAct loop     │◀── Claude + tool use
              │                 │      • rag_search   → $vectorSearch
              │  think → act    │      • document_lookup
              │    → observe    │      • calculator
              └────────┬────────┘
                       ▼
              Answer + reasoning trace
```

---

## 🚀 What Makes It Different

| | |
|---|---|
| **MongoDB-native vectors** | No Pinecone, no Weaviate, no second database to operate |
| **Real ReAct, not a RAG wrapper** | The model decides which tool to call and when to stop |
| **Visible reasoning** | Full thought/action/observation trace surfaced in the UI |
| **Graceful degradation** | Missing keys disable features instead of crashing the app |
| **Config-driven personas** | New analyst persona = four lines of YAML |
| **Benchmarked retrieval** | Model swaps are backed by a measured accuracy number |

---

## 🛠️ Roadmap

**Retrieval quality**
- [ ] Voyage reranking pass on `$vectorSearch` results
- [ ] Hybrid search: add a `$match` metadata stage (category, source, timestamp)
- [ ] Semantic chunking to replace the fixed 300-word window
- [ ] Attach source metadata to stored chunks (currently only `chunk` + `embedding`)

**Ops**
- [ ] Per-call cost logging for Voyage, OpenAI, and Anthropic
- [ ] `setup.sh` for venv + dependency install
- [ ] Tests for `rag.py` and `react_agent.py`
- [ ] Pin `whisper` in `requirements.txt` or document it as an optional extra

**Product**
- [ ] Custom prompt templates via YAML (extend the existing `agents/config.yaml` pattern)
- [ ] Unify `hugginglit.py` and `huggingparser.py` — one UI, not two
- [ ] Public demo on Hugging Face Spaces
- [ ] Explore lightweight fine-tuning for domain-specific corpora

**Cleanup**
- [ ] `huggingchat.py` and `hugginglit.py` are byte-identical duplicates — delete one
- [ ] `test.audio.pl` and `test_audio.mp3` sit in the repo root — move to `tests/fixtures/`
- [ ] Add a `.gitignore`; the repo isn't under version control yet
