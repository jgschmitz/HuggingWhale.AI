# HuggingWhale v2 — implemented stack

See [QUICKSTART.md](QUICKSTART.md) for setup and limits. The original README and architecture image are retained.

| Layer | Implementation |
|---|---|
| UI | Streamlit, navy and cream |
| API | FastAPI, bearer token mapped to tenant and principal |
| Originals | S3, content-addressed keys, captured versions or ETags |
| Text extraction | pypdf and UTF-8 decoding |
| Chunking + embeddings | Voyage context-4 REST API, auto chunking enabled |
| Jobs | Atlas-backed polling queue, leases, retries |
| Serving | Atlas chunks and live document manifests |
| Retrieval | Vector Search + keyword Search + reciprocal rank fusion |
| Reranking | Voyage rerank-2.5 |
| Answers | Optional OpenAI Chat Completions REST API |
| Feedback | Atlas events with 30-day TTL |
| Evaluation | Document-ID hit rate and reciprocal rank smoke tests |

S3 is canonical source storage. Search indexes are served by Atlas.
LangChain, Gradio, local Transformer models, and persona simulation have been removed.
No persistent agent memory or S3-native search engine is implemented.
