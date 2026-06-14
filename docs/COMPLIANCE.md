# Financial-marketing compliance guardrails

Finance content carries real regulatory and reputational risk. This system treats
compliance as a **first-class, non-optional gate**, not a soft suggestion.

## Where it's enforced

1. **Brand profile (`config/brand.yaml` → `compliance`)** — the rules: banned
   claims, required disclaimer, and "must" obligations. This is the source of truth.
2. **Every agent's system prompt** — the brand profile (including compliance rules)
   is injected into all agents, so generation is compliant by construction.
3. **Verify agent — deterministic scan** — `VerificationAgent._deterministic_compliance`
   does a hard string scan for banned-claim patterns *in code*. If a banned claim is
   found, the item is force-failed (`passed=False`, `compliance_ok=False`) regardless
   of what the LLM concluded. This is the safety net the model cannot override.
4. **Verify agent — LLM review** — a low-temperature reviewer also checks disclaimer
   presence, brand voice, platform fit, and factual sanity, returning prioritised
   issues.
5. **Human review gate** — nothing publishes without explicit human approval.

## The rules (defaults — set these for your jurisdiction)

- **Educational only.** No individualised "you should buy/sell X" advice.
- **No banned claims:** guaranteed returns, risk-free, "double your money",
  get-rich-quick, "can't lose", guaranteed multibagger, etc.
- **Disclaimer required** whenever specific instruments or returns are discussed.
- **Risk always disclosed** — outcomes framed as uncertain.

## ⚠️ Set your jurisdiction

The defaults are generic. Edit `config/brand.yaml → compliance.jurisdiction_note`
and the disclaimer for your actual regulator (e.g. **SEBI** in India, **FCA** in the
UK, **SEC/FINRA** in the US). Financial-promotion rules differ materially by market —
have a qualified compliance person sign off on the disclaimer text and the banned-claim
list before going live.

## Testing

`tests/test_pipeline.py::test_compliance_blocks_banned_claims` proves a
guaranteed-returns post is hard-blocked even in mock mode. Keep adding cases as you
tune the rules.
