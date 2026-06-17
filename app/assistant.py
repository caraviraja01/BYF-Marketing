"""The YourChartered.AI Q&A brain.

Answers finance / tax / accounting / startup questions in the Beyond Your Finance
voice, always closing with the required compliance disclaimer. Runs live on Claude
when an API key is present; otherwise returns a useful, on-brand mock answer so the
whole product works offline.
"""
from __future__ import annotations

from .brand import load_brand
from .llm import LLMError, get_llm

_MAX_HISTORY = 12  # turns of context sent to the model


def _system_prompt() -> str:
    brand = load_brand()
    disclaimer = (brand.compliance.get("required_disclaimer") or "").strip()
    return f"""You are YourChartered.AI, the AI finance assistant from {brand.name} \
({brand.get('tagline', '')}). You help startup founders, SMEs, business owners and \
the general public with questions about finance, taxation, accounting, compliance, \
fundraising and startups — with a strong focus on the Indian context (GST, Income \
Tax, TDS, MCA/ROC compliance, BRSR/ESG) while still handling general queries.

How to answer:
- Be clear, practical and accurate. Lead with a direct answer, then the key details.
- Use simple language; explain jargon. Prefer short paragraphs, bullets and steps.
- Use real-world examples and numbers where helpful, but never invent specific rates,
  thresholds or deadlines you are unsure about — say they should be verified.
- Stay in a warm, credible, no-hype advisor voice. Never use fear-based selling.

Hard rules:
- NEVER promise guaranteed outcomes (e.g. "guaranteed funding", "100% tax savings",
  "assured growth"). Avoid misleading or absolute financial claims.
- This is educational information, NOT personalised legal/tax/financial advice.
- When a question is complex, high-stakes, or needs someone's specific numbers,
  encourage the user to use the "Connect an Expert" button to speak with a {brand.name}
  chartered accountant live.
- End EVERY answer with this exact disclaimer on its own line:
  "{disclaimer}"
"""


def _mock_answer(question: str) -> str:
    brand = load_brand()
    disclaimer = (brand.compliance.get("required_disclaimer") or "").strip()
    return (
        f"Here's a general overview on **{question.strip().rstrip('?')}**.\n\n"
        "This is YourChartered.AI running in offline preview mode (no AI key configured), "
        "so this is a placeholder rather than a tailored answer. With a live key, I'd give "
        "you a clear, step-by-step explanation grounded in current Indian finance, tax and "
        "compliance rules.\n\n"
        "A few things I'd typically cover:\n"
        "- What the rule or concept means in plain language\n"
        "- The practical steps or numbers that apply to your situation\n"
        "- Common mistakes founders and businesses make here\n\n"
        "For anything specific to your business, tap **Connect an Expert** below to speak "
        f"with a {brand.name} chartered accountant live.\n\n"
        f"{disclaimer}"
    )


def answer_question(question: str, history: list[dict[str, str]] | None = None) -> str:
    """Return an assistant answer for ``question`` given prior ``history``.

    ``history`` is a list of {"role": "user"|"assistant", "content": str}. Falls back
    to a deterministic on-brand answer when the LLM is disabled or errors out.
    """
    llm = get_llm()
    if not llm.enabled:
        return _mock_answer(question)

    messages: list[dict[str, str]] = []
    for turn in (history or [])[-_MAX_HISTORY:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": question})

    try:
        return llm.generate_text(system=_system_prompt(), messages=messages, max_tokens=1600)
    except LLMError:
        return _mock_answer(question)


def title_for(question: str) -> str:
    """Short conversation title derived from the first question."""
    q = " ".join(question.split())
    return (q[:60] + "…") if len(q) > 60 else (q or "New question")
