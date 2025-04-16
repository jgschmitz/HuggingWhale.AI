import yaml

class Agent:
    def __init__(self, name, persona, instructions):
        self.name = name
        self.persona = persona
        self.instructions = instructions

    def chat(self, message):
        # Placeholder logic for chatting
        return f"Hello from {self.name}! You said: {message[:260]}..."

def load_agents(config_path="agentsConfig.YAML"):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    agents = []
    for agent_conf in config.get('agents', []):
        agent = Agent(
            name=agent_conf['name'],
            persona=agent_conf['persona'],
            instructions=agent_conf['instructions']
        )
        agents.append(agent)
    return agents

def run_agents_on_text(agent_list, text):
    results = {}
    for agent in agent_list:
        results[agent.name] = agent.chat(text)
    return results
