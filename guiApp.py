from whale_core import parser, agents
import gradio as gr

print("🐋 Welcome to HuggingWhale.AI")
print("Drop your chaos here and we'll pretend to make sense of it...\n")

def process_file(uploaded_file):
    try:
        # Parse and embed the file
        doc = parser.parse_file(uploaded_file.name)
        chunks = parser.chunk_and_embed(doc)

        # Load agent configs
        agent_cfgs = agents.load_agents("agents/config.yaml")

        # Run simulated agent conversations
        responses = agents.run_agents_on_text(agent_cfgs, doc)

        # Format response output
        output = ""
        for name, reply in responses.items():
            output += f"\n🤖 {name} says:\n{reply}\n"

        return output.strip()

    except Exception as e:
        return f"💥 Oops! Something went wrong:\n{str(e)}"

# Launch Gradio GUI
gr.Interface(
    fn=process_file,
    inputs=gr.File(label="📄 Upload your PDF or Text file"),
    outputs=gr.Textbox(label="🧠 Agent Responses", lines=20),
    title="HuggingWhale.AI",
    description="Drop a chaotic file. Let our agents attempt to decode the madness."
).launch()
