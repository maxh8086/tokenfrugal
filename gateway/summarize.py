"""Enforce the 150-300 token summary cap in code (second summarizing pass, then hard trim)."""
from openai import OpenAI

from .config import LLM_API_KEY, OLLAMA_URL, SUMMARY_MAX_TOKENS, SUMMARY_MIN_TOKENS

_client = OpenAI(base_url=OLLAMA_URL, api_key=LLM_API_KEY)


def tokens(text: str) -> int:
    return max(1, len(text) // 4)  # cheap estimate, avoids a tokenizer dependency


def hard_trim(text: str, limit: int = SUMMARY_MAX_TOKENS) -> str:
    if tokens(text) <= limit:
        return text
    cut = text[: limit * 4 - 12]  # leave room for the suffix
    return (cut.rsplit(".", 1)[0] + ". [trimmed]") if "." in cut else cut + " [trimmed]"


def summarize(model: str, text: str, task: str) -> str:
    if SUMMARY_MIN_TOKENS <= tokens(text) <= SUMMARY_MAX_TOKENS:
        return text
    for _ in range(2):
        r = _client.chat.completions.create(
            model=model, temperature=0.1, max_tokens=SUMMARY_MAX_TOKENS,
            messages=[{"role": "system", "content":
                       f"Summarize in {SUMMARY_MIN_TOKENS}-{SUMMARY_MAX_TOKENS} tokens. Keep file paths, "
                       "numbers, verdicts, next actions. No preamble, no filler."},
                      {"role": "user", "content": f"Task: {task}\n\nResult:\n{text}"}])
        text = (r.choices[0].message.content or "").strip() or text
        if tokens(text) <= SUMMARY_MAX_TOKENS:
            return text
    return hard_trim(text)
