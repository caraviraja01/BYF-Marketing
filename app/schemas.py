"""Pydantic contracts that flow between agents.

These are the typed hand-off shapes — each agent consumes the previous agent's
output and emits the next. Keeping them explicit makes the pipeline easy to reason
about, validate, and test.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

# ── 1. Research ───────────────────────────────────────────────────────────────


class TrendingTopic(BaseModel):
    title: str
    why_now: str = Field(description="Why this is timely / trending right now")
    angle: str = Field(description="The BYF-specific angle to take")
    relevance_score: int = Field(ge=1, le=10)


class CompetitorInsight(BaseModel):
    competitor: str
    what_they_did: str
    performance_signal: str = Field(description="Observed traction / engagement signal")
    takeaway: str = Field(description="What BYF should learn or do differently")


class ResearchBrief(BaseModel):
    summary: str
    trending_topics: list[TrendingTopic]
    competitor_insights: list[CompetitorInsight] = []
    content_gaps: list[str] = Field(default_factory=list)
    recommended_focus: str


# ── 2. Strategy ───────────────────────────────────────────────────────────────


class ContentIdea(BaseModel):
    title: str
    pillar: str
    platform: str
    format: str = Field(description="e.g. reel, carousel, thread, short, long-form post")
    funnel_stage: str = Field(description="awareness | consideration | conversion")
    hook: str
    key_message: str
    cta: str


class CalendarEntry(BaseModel):
    day: str = Field(description="e.g. 'Day 1' or 'Mon' — when to publish")
    platform: str
    pillar: str
    format: str
    title: str
    funnel_stage: str


class ContentStrategy(BaseModel):
    rationale: str
    ideas: list[ContentIdea] = Field(description="Ideas that will be fully produced this cycle")
    calendar_7_day: list[CalendarEntry] = Field(
        default_factory=list, description="A concrete 7-day posting plan"
    )
    monthly_themes: list[str] = Field(
        default_factory=list, description="Weekly themes for a 30-day view"
    )
    posting_notes: str = ""


# ── 3. Script ─────────────────────────────────────────────────────────────────


class Script(BaseModel):
    angle: str = Field(default="", description="Short label for this variant's angle/approach")
    platform: str
    format: str
    hook: str
    body: str = Field(description="Full caption / script body, platform-formatted")
    cta: str
    hashtags: list[str] = Field(default_factory=list)
    visual_direction: str = Field(default="", description="Notes for the creative agent")
    estimated_duration_sec: int | None = None


class ScriptSet(BaseModel):
    """Multiple script variants for one content idea — the human picks one."""

    variants: list[Script] = Field(description="Distinct script options (aim for 3)")


# ── 4. Creative ───────────────────────────────────────────────────────────────


class CreativeAsset(BaseModel):
    concept: str = Field(default="", description="Short label for this variant's visual concept")
    type: str = Field(description="image | carousel | video | brief")
    status: str = Field(description="generated | generating | brief_only | failed")
    provider: str = Field(default="", description="canva | higgsfield | none")
    title: str
    asset_url: str | None = None
    thumbnail_url: str | None = None
    canva_design_id: str | None = None
    higgsfield_request_id: str | None = None
    brief: str = Field(description="Creative brief / spec used or for a designer")
    slides: list[str] = Field(default_factory=list, description="Per-slide copy for carousels")
    error: str | None = None


class CreativeSet(BaseModel):
    """Multiple creative concepts for one content idea — the human picks one."""

    variants: list[CreativeAsset] = Field(description="Distinct creative options (aim for 3)")


# ── 5. Verification ───────────────────────────────────────────────────────────


class VerificationIssue(BaseModel):
    severity: str = Field(description="blocker | warning | nit")
    category: str = Field(description="compliance | brand_voice | platform | factual")
    detail: str
    suggested_fix: str


class VerificationResult(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100, description="Overall readiness score")
    issues: list[VerificationIssue] = Field(default_factory=list)
    compliance_ok: bool
    summary: str


# ── 6. Analytics ──────────────────────────────────────────────────────────────


class PerformanceMetrics(BaseModel):
    platform: str
    impressions: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    clicks: int = 0
    follows: int = 0
    engagement_rate: float = 0.0


class AnalyticsInsight(BaseModel):
    headline: str
    what_worked: list[str] = Field(default_factory=list)
    what_underperformed: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    next_topic_suggestions: list[str] = Field(default_factory=list)
