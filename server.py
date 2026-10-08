"""Minimal stdio MCP server exposing a local OpenAI-compatible LLM as tools (clean-room implementation).

Inspired by csabakecskemeti/cc_token_saver_mcp. Configure the endpoint in .env (see .env.example).
"""
import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from openai import OpenAI

load_dotenv()
URL = os.getenv("TOKENFRUGAL_LLM_URL") or os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
MODEL = os.getenv("LOCAL_MODEL_NAME", "llama3.2:3b-16k")
client = OpenAI(base_url=URL, api_key=os.getenv("TOKENFRUGAL_LLM_API_KEY", "ollama"))
mcp = FastMCP("tokenfrugal-local-llm")

SYSTEMS = {
    "code_review": "You are a careful code reviewer. List concrete issues, most severe first.",
    "documentation": "You write concise, accurate technical documentation.",
    "refactor": "You propose minimal, behavior-preserving refactors with code.",
    "general": "You are a helpful assistant. Be concise.",
}


def _ask(system: str, user: str, temperature: float = 0.2, max_tokens: int | None = None) -> str:
    try:
        r = client.chat.completions.create(
            model=MODEL, temperature=temperature, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return r.choices[0].message.content or ""
    except Exception as e:  # returned as text so the calling agent can react
        return f"Error querying local LLM: {e}"


@mcp.tool()
def query_local_llm(prompt: str, temperature: float = 0.2, max_tokens: int | None = None) -> str:
    """Offload a small, self-contained task (summary, boilerplate, regex, docstring) to the local LLM."""
    return _ask(SYSTEMS["general"], prompt, temperature, max_tokens)


@mcp.tool()
def query_local_llm_with_context(context: str, task: str, task_type: str = "general") -> str:
    """Run a task over supplied context. task_type: code_review, documentation, refactor or general."""
    return _ask(SYSTEMS.get(task_type, SYSTEMS["general"]), f"Context:\n{context}\n\nTask:\n{task}")


if __name__ == "__main__":
    mcp.run()
