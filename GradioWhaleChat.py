def whale_chat(file):
    doc = parser.parse_file(file.name)
    responses = agents.run_agents_on_text(agents.load_agents("agents/config.yaml"), doc)
    return "\n\n".join([f"🤖 {k}: {v}" for k, v in responses.items()])

gr.Interface(fn=whale_chat, inputs="file", outputs="text", title="🐋 HuggingWhale Playground").launch()
