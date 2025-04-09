from whale_core import parse_file, run_agents

doc = parse_file("examples/sample_inputs/sample.pdf")
responses = run_agents(doc, config_path="agents/config.yaml")

for agent, response in responses.items():
    print(f"{agent} says:\n{response}\n")
