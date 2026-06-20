import os

import anthropic

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")


def _api_key():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st

            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    if not key:
        raise ValueError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY "
            "(env var or .streamlit/secrets.toml)."
        )
    return key


def get_client():
    return anthropic.Anthropic(api_key=_api_key())


def chat(messages, system=None, tools=None, model=None, max_tokens=1024, temperature=0.2):
    client = get_client()
    kwargs = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
    return client.messages.create(**kwargs)
jefferyschmitz@M-KXQ9026J7V whale_core % 
jefferyschmitz@M-KXQ9026J7V whale_core % 
jefferyschmitz@M-KXQ9026J7V whale_core % 
jefferyschmitz@M-KXQ9026J7V whale_core % ls
__pycache__     llm.py          rag.py          tools.py
agents.py       parser.py       react_agent.py
jefferyschmitz@M-KXQ9026J7V whale_core % cat tools.py
"""Tools the ReAct agent can call autonomously."""
import ast
import operator
import re

from whale_core import rag

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("Unsupported expression")


def calculator(expression):
    """Safely evaluate a basic arithmetic expression."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree.body))
    except Exception as e:
        return f"Could not evaluate '{expression}': {e}"


def rag_search(query, top_k=3):
    """Semantic search over the MongoDB vector store via Voyage embeddings."""
    try:
        chunks = rag.query_rag(query, top_k=top_k)
        if not chunks:
            return "No matching chunks found in the vector store."
        return "\n\n---\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(chunks))
    except Exception as e:
        return f"rag_search failed: {e}"


def document_lookup(keyword, document, window=300):
    """Keyword search within the currently loaded document text."""
    if not document:
        return "No document is loaded."
    matches = []
    for m in re.finditer(re.escape(keyword), document, flags=re.IGNORECASE):
        start = max(0, m.start() - window // 2)
        end = min(len(document), m.end() + window // 2)
        matches.append("..." + document[start:end].strip() + "...")
        if len(matches) >= 3:
            break
    return "\n\n".join(matches) if matches else f"'{keyword}' not found in the document."


TOOL_SCHEMAS = [
    {
        "name": "rag_search",
        "description": "Semantic vector search over the indexed knowledge base. "
                       "Use for conceptual questions where exact wording is unknown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language search query."},
                "top_k": {"type": "integer", "description": "Number of chunks to return.", "default": 3},
            },
            "required": ["query"],
        },
    },
    {
        "name": "document_lookup",
        "description": "Exact keyword search inside the document currently loaded in the "
                       "session. Use to find specific terms, names, or numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Exact term to locate."},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "calculator",
        "description": "Evaluate a basic arithmetic expression (+, -, *, /, **, %).",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "e.g. '12 * (3 + 4)'"},
            },
            "required": ["expression"],
        },
    },
]


def dispatch(name, tool_input, document=None):
    if name == "rag_search":
        return rag_search(tool_input["query"], tool_input.get("top_k", 3))
    if name == "document_lookup":
        return document_lookup(tool_input["keyword"], document)
    if name == "calculator":
        return calculator(tool_input["expression"])
    return f"Unknown tool: {name}"
