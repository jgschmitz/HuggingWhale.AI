import logging
from pathlib import Path

import gradio as gr
from whale_core import agents, parser, react_agent


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
AGENT_CONFIG_PATH = BASE_DIR / "agents" / "config.yaml"

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_DOCUMENT_CHARS = 50_000         # Adjust for your model's context window.
MAX_QUESTION_CHARS = 4_000

# Serialize document processing and agent calls until whale_core's
# thread safety and request isolation have been verified.
WORKER_GROUP = "whale-core"


def process_file(file_path):
    """Return persona output, session document, and cleared agent output."""
    if not file_path:
        return "", "", ""

    try:
        path = Path(file_path)

        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return "⚠️ Please upload a PDF or TXT file.", "", ""

        if not path.is_file():
            return "⚠️ That upload is no longer available. Please upload it again.", "", ""

        if path.stat().st_size > MAX_UPLOAD_BYTES:
            return "⚠️ Please upload a file smaller than 10 MB.", "", ""

        document = parser.parse_file(str(path))

        if not isinstance(document, str) or not document.strip():
            return (
                "⚠️ No readable text was found. Scanned PDFs may need OCR.",
                "",
                "",
            )

        document = document.strip()

        if len(document) > MAX_DOCUMENT_CHARS:
            return (
                f"⚠️ This document exceeds the "
                f"{MAX_DOCUMENT_CHARS:,}-character limit. "
                "Please upload a smaller document.",
                "",
                "",
            )

        # Deliberately avoid a potentially shared embedding index.
        # Add embeddings only when storage AND retrieval are scoped
        # to the current user/session and document.
        agent_configs = agents.load_agents(str(AGENT_CONFIG_PATH))
        responses = agents.run_agents_on_text(agent_configs, document)

        output = "\n\n".join(
            f"🤖 {name} says:\n{reply}"
            for name, reply in responses.items()
        )

        # Store only successfully processed documents.
        # Clear any answer associated with the previous upload.
        return output or "No agent responses were returned.", document, ""

    except Exception:
        logger.exception("Document processing failed")
        # Don't leave an older document active after a failed upload.
        return (
            "💥 Couldn't process that file. Try another file or try again later.",
            "",
            "",
        )


def ask_agent(question, document):
    question = (question or "").strip()

    if not question:
        return "Ask me something about the document—or anything else."

    if len(question) > MAX_QUESTION_CHARS:
        return (
            f"⚠️ Please keep your question under "
            f"{MAX_QUESTION_CHARS:,} characters."
        )

    try:
        answer, _trace = react_agent.run(
            question,
            document=document or None,
        )

        # Don't expose raw internal traces in the UI.
        return str(answer) if answer else "The agent returned no answer."

    except Exception:
        logger.exception("Agent request failed")
        return "💥 Couldn't complete that request. Please try again later."


with gr.Blocks(title="HuggingWhale.AI") as demo:
    # Session-specific, rather than shared between all users.
    document_state = gr.State("")

    gr.Markdown(
        "# 🐋 HuggingWhale.AI\n"
        "Drop a chaotic file. Then let the ReAct agent decode it."
    )
    gr.Markdown(
        "Upload a PDF or TXT file up to **10 MB**. "
        "Document text is limited to **50,000 characters**."
    )

    with gr.Tab("📄 Persona Agents"):
        file_in = gr.File(
            label="Upload your PDF or text file",
            type="filepath",
            file_count="single",
            file_types=[".pdf", ".txt"],
        )

        persona_out = gr.Textbox(
            label="🧠 Agent Responses",
            lines=20,
            interactive=False,
        )

    with gr.Tab("🤖 ReAct Agent"):
        question_in = gr.Textbox(
            label="Ask the agent",
            placeholder="What are the main points of this document?",
            lines=2,
        )
        ask_btn = gr.Button("Run agent", variant="primary")

        agent_out = gr.Textbox(
            label="Agent answer",
            lines=20,
            interactive=False,
        )

    # Register after all output components have been created.
    file_in.change(
        fn=process_file,
        inputs=[file_in],
        outputs=[persona_out, document_state, agent_out],
        concurrency_id=WORKER_GROUP,
        concurrency_limit=1,
        show_progress="full",
    )

    # Button click and keyboard submission use the same handler.
    gr.on(
        triggers=[ask_btn.click, question_in.submit],
        fn=ask_agent,
        inputs=[question_in, document_state],
        outputs=[agent_out],
        concurrency_id=WORKER_GROUP,
        concurrency_limit=1,
        show_progress="full",
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    demo.queue(max_size=32).launch(
        max_file_size=MAX_UPLOAD_BYTES,
        show_error=False,
    )
