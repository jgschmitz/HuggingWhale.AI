"""Run with streamlit run app.py. The UI talks only to the authenticated API."""
from urllib.parse import quote

import httpx
import streamlit as st

st.set_page_config(page_title="HuggingWhale.ai", page_icon="🐳", layout="wide")
st.markdown("""<style>
 .stApp {background:#f2f0e5;color:#15273a}
 [data-testid="stSidebar"] {background:#e4e7df}
 h1,h2,h3 {color:#15273a!important;letter-spacing:-.04em}
 .stButton>button,.stDownloadButton>button {border-radius:0;border:1px solid #15273a;
 background:#ffba7a;color:#15273a;box-shadow:3px 3px #15273a;font-family:monospace}
 .banner {background:#15273a;color:#f2f0e5;padding:26px 30px;border-bottom:5px solid #ffba7a}
 .banner strong {font-size:34px;letter-spacing:-1.5px}
 .banner p {font-family:monospace;font-size:13px;margin:8px 0 0}
 </style>""", unsafe_allow_html=True)
st.markdown('<div class="banner"><strong>HuggingWhale.ai / hug your data.</strong>'
            '<p>Object storage. Searchable context. Answers with sources.</p></div>', unsafe_allow_html=True)
with st.sidebar:
    st.subheader("Connect to your whale")
    api = st.text_input("API URL", "http://127.0.0.1:8000").rstrip("/")
    token = st.text_input("API token", type="password")
    st.caption("Keys and Atlas connections live in the API's config.local.json. No .env required.")
    if st.button("Connect"):
        st.session_state.pop("identity", None)
        st.session_state.pop("result", None)
        try:
            r = httpx.get(api + "/identity", headers={"Authorization": f"Bearer {token}"}, timeout=10)
            r.raise_for_status()
            st.session_state.identity = r.json()
            st.session_state.connection = (api, token)
        except Exception:
            st.error("Could not connect. Check the API URL and token.")
if "identity" not in st.session_state or st.session_state.get("connection") != (api, token):
    st.info("Start the API and connect in the sidebar to upload, search, or ask questions.")
    st.stop()
identity = st.session_state.identity
st.caption(f"TENANT / {identity['tenant']}     PRINCIPAL / {identity['principal']}")


def request(method, path, **kwargs):
    try:
        r = httpx.request(method, api + path, headers={"Authorization": f"Bearer {token}"},
                          timeout=180, **kwargs)
        if not r.is_success:
            st.error(r.json().get("detail", "API request failed"))
            return None
        return r
    except Exception:
        st.error("API request failed. Verify that the service is running.")
        return None


search_tab, docs_tab, ops_tab = st.tabs(["Search + ask", "Knowledge sources", "Operations"])
with search_tab:
    question = st.text_area("What do you want to know?", placeholder="Ask across your indexed documents…",
                            max_chars=4000)
    a, b, c = st.columns(3)
    top_k = a.slider("Sources", 1, 20, 6)
    rerank = b.checkbox("Voyage reranking", True)
    answer = c.checkbox("Generate an answer", False)
    if st.button("Dive in", disabled=not question.strip()):
        st.session_state.pop("result", None)
        with st.spinner("Retrieving relevant context…"):
            r = request("POST", "/search", json={"question": question, "top_k": top_k,
                                                "rerank": rerank, "answer": answer})
            if r is not None:
                st.session_state.result = r.json()
    result = st.session_state.get("result")
    if result:
        st.caption(f"{result['latency_ms']:,.0f} ms · {len(result['sources'])} sources · trace {result['trace_id']}")
        if result.get("answer"):
            st.markdown(result["answer"])
        for hit in result["sources"]:
            with st.expander(f"[{hit['citation']}] {hit['filename']} · chunk {hit['chunk_index'] + 1}"):
                st.write(hit["text"])
                st.caption(f"Document: {hit['document_id']} · rerank: {hit.get('rerank_score')}")
        if not result["sources"]:
            st.info("No matching accessible sources. Confirm ingestion succeeded and indexes are ready.")
        with st.expander("Usage"):
            st.json(result["usage"])
        up, down = st.columns(2)
        for col, label, helpful in ((up, "Helpful", True), (down, "Needs work", False)):
            if col.button(label):
                if request("POST", "/feedback/" + result["trace_id"], json={"helpful": helpful}) is not None:
                    st.success("Feedback recorded")
with docs_tab:
    if identity["admin"]:
        with st.form("upload"):
            file = st.file_uploader("Source file", type=["pdf", "txt", "md", "csv", "json"])
            doc_id = st.text_input("Stable document ID", placeholder="employee-handbook")
            access = st.text_input("Access principals, comma separated", "tenant",
                                   help="tenant means all readers in this tenant; otherwise list principal names.")
            send = st.form_submit_button("Queue ingestion")
        if send and file and doc_id:
            r = request("POST", "/documents", data={"document_id": doc_id, "allowed_principals": access},
                        files={"file": (file.name, file.getvalue(), file.type)})
            if r is not None:
                st.json(r.json())
                if r.json().get("job_id"):
                    st.session_state.job_id = r.json()["job_id"]
    if st.button("Refresh sources"):
        r = request("GET", "/documents")
        if r is not None:
            st.dataframe(r.json())
    source_id = st.text_input("Document ID to download")
    if st.button("Fetch original", disabled=not source_id):
        r = request("GET", f"/documents/{quote(source_id, safe='')}/source")
        if r is not None:
            st.download_button("Download source", r.content, file_name="source.bin")
    if identity["admin"]:
        delete_id = st.text_input("Document ID to remove from search")
        confirm = st.checkbox("Remove indexed content; retain the original S3 object")
        if st.button("Remove source from search", disabled=not delete_id or not confirm):
            r = request("DELETE", "/documents/" + quote(delete_id, safe=""))
            if r is not None:
                st.success("Removed from search. S3 retention follows your bucket policy.")
with ops_tab:
    st.code("python -m whale_core.cli setup\npython -m whale_core.cli indexes\npython -m whale_core.cli worker")
    st.caption("Run setup and index creation once, then keep a worker running. Search indexes build asynchronously.")
    if identity["admin"]:
        if st.button("Check readiness"):
            r = request("GET", "/ready")
            if r is not None:
                st.json(r.json())
        job_id = st.text_input("Job ID", value=st.session_state.get("job_id", ""))
        if st.button("Refresh job", disabled=not job_id):
            r = request("GET", "/jobs/" + quote(job_id, safe=""))
            if r is not None:
                st.json(r.json())
    else:
        st.info("Ingestion jobs and readiness details require an admin token.")
