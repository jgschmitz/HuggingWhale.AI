from whale_core import parser, agents

print("🐋 Welcome to HuggingWhale.AI")
print("Drop your chaos here and we'll pretend to make sense of it...\n")

# Fake file parsing (replace with actual PDF path later)
doc = parser.parse_file("examples/sample.pdf")
chunks = parser.chunk_and_embed(doc)

# Load your agents
agent_cfgs = agents.load_agents("agents/config.yaml")

# Simulate agent convo
responses = agents.run_agents_on_text(agent_cfgs, doc)

# Output agent responses
for name, reply in responses.items():
    print(f"\n🤖 {name} says:\n{reply}")
