def log_embedding_cost(provider: str, num_tokens: int):
    # Define simple token cost rates (you could load from config)
    token_cost_per_1k = {
        "openai": 0.0001,   # dollars per 1000 tokens
        "voyage": 0.00008   # example, adjust for real Voyage pricing
    }
    
    rate = token_cost_per_1k.get(provider.lower())
    if rate is None:
        print(f"[WARN] Unknown provider: {provider}")
        return

    cost = (num_tokens / 1000) * rate
    print(f"[COST LOG] Provider: {provider.upper()}, Tokens: {num_tokens}, Estimated Cost: ${cost:.6f}")
