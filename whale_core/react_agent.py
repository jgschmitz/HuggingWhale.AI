"""A real ReAct agent: Claude reasons, calls tools, observes results, and loops."""
from whale_core import llm, tools

SYSTEM_PROMPT = (
    "You are HuggingWhale, an autonomous research agent. Answer the user's question "
    "by reasoning step by step and using the available tools when they help. "
    "Prefer rag_search for conceptual lookups, document_lookup for exact terms in the "
    "loaded document, and calculator for arithmetic. Call tools only when needed. "
    "When you have enough information, stop calling tools and give a clear final answer "
    "that cites which tool results you relied on."
)


def run(question, document=None, max_steps=6, verbose=True):
    """Run the reason-act-observe loop and return (answer, trace)."""
    context = ""
    if document:
        context = f"\n\nA document is loaded in this session (excerpt):\n{document[:2000]}"

    messages = [{"role": "user", "content": question + context}]
    trace = []

    for step in range(max_steps):
        response = llm.chat(
            messages,
            system=SYSTEM_PROMPT,
            tools=tools.TOOL_SCHEMAS,
            max_tokens=1024,
        )

        for block in response.content:
            if block.type == "text" and block.text.strip():
                trace.append(f"💭 Thought: {block.text.strip()}")

        if response.stop_reason != "tool_use":
            answer = "".join(b.text for b in response.content if b.type == "text").strip()
            trace.append(f"✅ Final answer: {answer}")
            return answer, trace

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            trace.append(f"🔧 Action: {block.name}({block.input})")
            result = tools.dispatch(block.name, block.input, document=document)
            trace.append(f"👁️ Observation: {result[:500]}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    fallback = "Reached the maximum number of reasoning steps without a final answer."
    trace.append(f"⚠️ {fallback}")
    return fallback, trace
