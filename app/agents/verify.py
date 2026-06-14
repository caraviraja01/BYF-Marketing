"""Agent 5 — Verification / QA & Compliance.

The safety gate before a human ever sees the content. Checks brand voice, platform
fit, factual sanity and — most importantly for a finance brand — regulatory
compliance. Banned-claim detection is done deterministically (not left to the LLM)
so it can never be 'reasoned away'.
"""
from __future__ import annotations

from typing import Any

from ..schemas import Script, VerificationIssue, VerificationResult
from .base import BaseAgent


class VerificationAgent(BaseAgent[VerificationResult]):
    name = "verify"
    role = "Verification — brand, platform & financial compliance"
    output_model = VerificationResult
    fast = True
    temperature = 0.2

    def expertise(self) -> str:
        return (
            "You are a meticulous compliance and brand-quality reviewer for a financial "
            "education brand. You check that content (a) stays strictly educational and "
            "never gives individualised buy/sell advice, (b) makes no guaranteed-return, "
            "risk-free or get-rich-quick claims, (c) includes the required disclaimer when "
            "instruments/returns are discussed, (d) matches the brand voice (warm, "
            "credible, no-hype), (e) fits the target platform's norms and limits, and "
            "(f) contains no obvious factual errors. Classify each issue as blocker, "
            "warning or nit, and give a concrete suggested fix. Be strict on compliance."
        )

    def build_user_prompt(
        self,
        *,
        script: dict[str, Any] | Script,
        creative: dict[str, Any] | None = None,
        **_: Any,
    ) -> str:
        data = script.model_dump() if isinstance(script, Script) else script
        rules = self.brand.compliance
        return (
            "Review this content for publication readiness.\n\n"
            f"SCRIPT:\n{data}\n\n"
            f"CREATIVE:\n{creative or '(brief only)'}\n\n"
            f"COMPLIANCE RULES TO ENFORCE:\n{rules}\n\n"
            "Return an overall pass/fail, a 0–100 readiness score, compliance_ok flag, a "
            "list of issues (severity, category, detail, suggested_fix), and a one-line "
            "summary. Any banned claim or a missing required disclaimer when instruments "
            "are discussed is a BLOCKER and must set passed=false and compliance_ok=false."
        )

    def _compliance_text(self, script: dict[str, Any]) -> str:
        return " ".join(
            str(script.get(k, ""))
            for k in ("hook", "body", "cta")
        ).lower()

    def _deterministic_compliance(self, script: dict[str, Any]) -> list[VerificationIssue]:
        """Hard, non-LLM scan for banned claims — compliance can't be 'reasoned away'."""
        text = self._compliance_text(script)
        issues: list[VerificationIssue] = []
        for phrase in self.brand.compliance.get("banned_claims", []):
            # Match on the salient words of each banned phrase.
            needles = [w for w in phrase.lower().replace("/", " ").split() if len(w) > 3]
            if needles and all(n in text for n in needles):
                issues.append(
                    VerificationIssue(
                        severity="blocker",
                        category="compliance",
                        detail=f"Detected banned claim pattern: '{phrase}'.",
                        suggested_fix="Remove the claim; reframe with honest, risk-aware language.",
                    )
                )
        return issues

    def run(self, **inputs: Any) -> VerificationResult:  # type: ignore[override]
        result = super().run(**inputs)
        script = inputs.get("script")
        script_data = script.model_dump() if isinstance(script, Script) else (script or {})
        hard_issues = self._deterministic_compliance(script_data)
        if hard_issues:
            result.issues = hard_issues + list(result.issues)
            result.passed = False
            result.compliance_ok = False
            result.score = min(result.score, 40)
            result.summary = "Blocked by compliance scan: " + result.summary
        return result

    def mock(
        self,
        *,
        script: dict[str, Any] | Script,
        creative: dict[str, Any] | None = None,
        **_: Any,
    ) -> VerificationResult:
        data = script.model_dump() if isinstance(script, Script) else script
        has_disclaimer = "not financial advice" in self._compliance_text(data)
        issues: list[VerificationIssue] = []
        if not has_disclaimer:
            issues.append(
                VerificationIssue(
                    severity="warning",
                    category="compliance",
                    detail="No disclaimer detected though the post discusses instruments.",
                    suggested_fix="Append the required educational-only disclaimer.",
                )
            )
        return VerificationResult(
            passed=True,
            score=88 if has_disclaimer else 72,
            compliance_ok=True,
            issues=issues,
            summary=(
                "On-brand and compliant — clear hook, honest framing, soft CTA."
                if has_disclaimer
                else "Solid draft; add the disclaimer before publishing."
            ),
        )
