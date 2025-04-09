from whale_core import parser, agents

doc = parser.parse_file("examples/sample.pdf")
chunks = parser.chunk_and_embed(doc)
agent_cfgs = agents.load_agents("agents/config.yaml")
responses = agents.run_agents_on_text(agent_cfgs, doc)

for name, reply in responses.items():
    print(f"\n🤖 {name} says:\n{reply}")
