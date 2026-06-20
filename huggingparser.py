from whale_core import parser, agents, react_agent
import gradio as gr

print("🐋 Welcome to HuggingWhale.AI")
print("Drop your chaos here and we'll pretend to make sense of it...\n")

# Holds the most recently parsed document text for the ReAct agent.
SESSION = {"document": ""}


def process_file(uploaded_file):
    try:
        doc = parser.parse_file(uploaded_file.name)
        SESSION["document"] = doc
        parser.chunk_and_embed(doc)

        agent_cfgs = agents.load_agents("agents/config.yaml")
        responses = agents.run_agents_on_text(agent_cfgs, doc)

        output = ""
        for name, reply in responses.items():
            output += f"\n🤖 {name} says:\n{reply}\n"
        return output.strip()

    except Exception as e:
        return f"💥 Oops! Something went wrong:\n{str(e)}"


def ask_agent(question):
    if not question or not question.strip():
        return "Ask me something about the document (or anything else)."
    try:
        answer, trace = react_agent.run(question, document=SESSION.get("document"))
        return answer + "\n\n---\n🧭 Reasoning trace:\n" + "\n".join(trace)
    except Exception as e:
        return f"💥 Agent error:\n{str(e)}"


with gr.Blocks(title="HuggingWhale.AI") as demo:
    gr.Markdown("# 🐋 HuggingWhale.AI\nDrop a chaotic file. Then let the ReAct agent decode it.")

    with gr.Tab("📄 Persona Agents"):
        file_in = gr.File(label="Upload your PDF or Text file")
        persona_out = gr.Textbox(label="🧠 Agent Responses", lines=20)
        file_in.change(process_file, inputs=file_in, outputs=persona_out)

    with gr.Tab("🤖 ReAct Agent"):
        question_in = gr.Textbox(label="Ask the agent", lines=2)
        ask_btn = gr.Button("Run agent")
        agent_out = gr.Textbox(label="Agent answer + reasoning", lines=20)
        ask_btn.click(ask_agent, inputs=question_in, outputs=agent_out)


if __name__ == "__main__":
    demo.launch()
