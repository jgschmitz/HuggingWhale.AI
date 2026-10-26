# 🐳 HuggingWhale v2 — start here

This is the new runnable stack. The existing `README.md`, logo, and architecture
image were preserved exactly as requested. Use **this guide** for installation;
the README's older installation and persona-agent descriptions are not the v2 contract.

## What you get

- S3 originals plus extracted text, with content-addressed object keys and source version references.
- Asynchronous ingestion through an Atlas-backed queue with leases and bounded retries.
- Voyage `voyage-context-4`: backend automatic chunking and contextualized embeddings.
- Atlas Vector Search plus keyword Search, combined with reciprocal rank fusion.
- Voyage reranking, optional OpenAI answers with numbered source references.
- Tenant/principal-scoped retrieval, authenticated source downloads, feedback, token usage, and latency.
- A navy/cream Streamlit interface and agent-facing HTTP API. No LangChain,
  local Transformer model downloads, fine-tuning scripts, Gradio, or `.env` dependency.

## 1. Prepare your machine

Use **Python 3.11 or newer** in a fresh virtual environment. Python 3.12 was used
for local verification; this package does not modify your older OpenAI demo environment.
The bundled Streamlit and PyMongo releases no longer support Python 3.10.

From the unzipped `HuggingWhale-v2` folder, on macOS/Linux:

```bash
bash setup.sh
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item config.example.json config.local.json
```

## 2. Plug in your connections

Edit `config.local.json`. This file is ignored by Git. You can put your demo keys
and Atlas URI directly in it. Do not commit a filled-in local configuration.

| Setting | What goes here |
|---|---|
| `mongo_uri` | Your Atlas SRV URI, database user, and password |
| `database` | New v2 database, default `huggingwhale_v2` |
| `s3_bucket`, `s3_region` | An existing private bucket and its AWS region |
| `voyage_api_key` | Voyage key with contextual embedding and reranking access |
| `embedding_model` | Default `voyage-context-4` |
| `dimensions`, `chunk_size` | Default 1024 dimensions and a 512-token target |
| `rerank_model` | Default `rerank-2.5` |
| `llm_api_key`, `llm_model` | Optional OpenAI key and a model supporting Chat Completions |
| `api_tokens` | Server-side tokens mapped to tenant, principal, and admin status |

Generate a token, then replace the example token in `api_tokens`:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

The token map is an initial local deployment mechanism. The API derives tenant
and principal from it; callers cannot select another tenant in a search body.
An admin can ingest/delete within their tenant. Read access still follows the ACL.
`allowed_principals: tenant` means every authenticated reader in that tenant;
otherwise use comma-separated principal names such as `jeffery,alex`.

AWS credentials use boto3's normal credential chain: an instance role, AWS SSO/profile,
or your existing AWS credential configuration. No AWS keys go into the browser.
For a non-default profile, set `AWS_PROFILE` in your shell before starting.
Bucket versioning is recommended; object keys also contain a content digest and reads
use a captured version ID, or an ETag precondition when versioning is unavailable.

The application needs `s3:PutObject`, `s3:GetObject`, `s3:GetObjectVersion`, and
`s3:ListBucket` (readiness) for its bucket/prefix. A KMS-encrypted bucket may also
require KMS permissions. The app does not create a bucket, open it publicly, or change
its retention/encryption policies.

Atlas needs network access from your machine, database read/write permissions,
and Search index management permissions for initial setup. Use an Atlas deployment
with Vector Search and Search available; plain local MongoDB cannot run those stages.

## 3. Create the indexes once

```bash
python -m whale_core.cli setup
python -m whale_core.cli indexes
```

The second command creates missing `hw_vector` and `hw_keyword` indexes. It does
not recreate indexes on every run. Run it again to inspect readiness: **both must
be queryable** before searching. Builds can take time.

Changing embedding dimensions requires a matching index. The setup checks existing
vector dimensions and rejects a mismatch rather than silently changing the index.
Use a new database or intentionally rebuild `hw_vector`, then re-ingest documents.
Changing the embedding model or chunk configuration also requires re-ingestion.
The service filters by a pipeline signature so incompatible old embeddings are excluded.

## 4. Launch everything

```bash
python start.py
```

- UI: <http://127.0.0.1:8501>
- Interactive API docs: <http://127.0.0.1:8000/docs>

Paste your API token into the UI sidebar and click **Connect**. The launcher starts
the API, worker, and UI together. Ctrl-C stops all three. It binds to localhost.

For individual processes in three terminals, use:

```bash
python -m uvicorn whale_core.api:app --host 127.0.0.1 --port 8000
python -m whale_core.cli worker
streamlit run app.py --server.address 127.0.0.1
```

## 5. First run

1. Upload `examples/handbook.md` in **Knowledge sources** with document ID `handbook`.
2. In **Operations**, refresh the returned job ID until it says `succeeded`.
3. Ask: “How much can I expense for learning materials?”
4. Leave answer generation off to return search hits, or turn it on after configuring
   the OpenAI fields. Reranking is independently selectable.
5. Expand source chunks and inspect usage. Feedback is associated with the request's trace ID.

PDF, UTF-8 TXT/Markdown, CSV, and JSON are accepted. CSV and JSON are treated as
text; this is not a relational query engine. OCR, audio transcription, HTML fetching,
and external connector polling are not included. Scanned PDFs with no text fail clearly.
Extracted text is limited to 100,000 characters by default. The character limit is
an application guard, not a token guarantee: Voyage's request limits still apply.
Oversized or rejected provider requests fail visibly; text is never silently truncated.

## Lifecycle and data handling

- Reusing a document ID queues a replacement. The previous successful version stays
  available until the replacement is staged and activated through a manifest pointer.
- Identical active uploads are skipped; identical pending uploads reuse the queued job.
- Old queued requests cannot overwrite a newer requested version. A failed ingestion
  preserves the previous successful revision and exposes its job status.
- Search results are checked against current manifests before external reranking,
  before answer generation, and before return. Stale deleted, unauthorized, or old
  revisions from a lagging Search index are discarded. Authorization is point-in-time;
  content already sent to a provider cannot be recalled.
- Removing a document tombstones its manifest and deletes indexed chunks. S3 originals
  and extracted text remain subject to your bucket retention policy. This operation is
  **removal from search**, not a promise of complete data erasure.
- Successful updates remove the previous active chunk revision. A worker crash can
  leave unreferenced staged chunks or S3 blobs; full orphan reclamation is not automated.
- Concurrent identical submissions can produce redundant jobs; deterministic source keys
  and manifest activation prevent duplicate active content. Index lag can briefly reduce
  recall after updates; an ingestion success is not an index-readiness guarantee.
- Telemetry stores token usage, latency, trace IDs, identities, and feedback, not raw questions,
  answers, or source text. Events expire after 30 days. Source content is sent to Voyage
  and, if enabled, retrieved content is sent to OpenAI. Provider policies apply.

## Agent/API integration

Agents can call `POST /search` with a bearer token and receive ranked context and citations.
This is a retrieval service, not an autonomous tool-executing agent runtime. Persistent
agent memory, conversation sessions, automatic cache tiering, and dollar-cost accounting
are future extensions; no simulated implementations are presented as working features.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Process liveness only |
| `GET /identity` | Authenticated token identity |
| `GET /ready` | Admin-only Mongo/S3 connectivity and Search readiness |
| `POST /documents` | Admin multipart upload → durable job |
| `GET /jobs/{id}` | Admin job status scoped to tenant |
| `GET /documents` | Accessible manifests, up to 200 |
| `GET /documents/{id}/source` | Authenticated download of the active original |
| `DELETE /documents/{id}` | Admin removal from indexed serving |
| `POST /search` | Hybrid retrieval, reranking, optional generation |
| `POST /feedback/{trace_id}` | Feedback on the authenticated principal's request |

`POST /search` JSON body:

```json
{"question":"What are our support hours?","top_k":6,"rerank":true,"answer":false}
```

## Verify and evaluate

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m whale_core.cli evaluate --cases examples/eval.json --tenant demo --principal jeffery
```

The automated tests use mongomock and HTTP/S3 doubles. They cover the API, access
boundaries, update/delete races, retry behavior, source mapping, provider request
contracts, and Streamlit startup. They do not emulate Lucene or prove live Atlas,
S3, Voyage, or OpenAI behavior. Run the sample ingestion and evaluation against your
own configured accounts for live validation. The two sample questions are a smoke
test, not a retrieval-quality benchmark.

## Deployment scope

This is a runnable local baseline. Before public hosting, add managed identity,
request-size enforcement at the gateway, rate limiting, TLS, operational alerting,
and deployment-specific isolation. No cloud infrastructure is provisioned by setup.
The worker currently polls once per second; worker and API must use the same configuration.
The queue is durable, but the single-document S3/manifest/job writes are not one distributed
transaction. A crash between submission writes can require resubmitting the upload.

S3 holds canonical files; Atlas holds the indexed serving copy. This does not implement
a turbopuffer-style search index directly on S3 and does not establish matching economics.
No benchmark or pricing-parity claim is made by this package.
