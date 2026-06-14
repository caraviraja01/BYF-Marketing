"""The six marketing agents."""
from .analytics import AnalyticsAgent
from .creative import CreativeAgent
from .research import ResearchAgent
from .script import ScriptAgent
from .strategy import StrategyAgent
from .verify import VerificationAgent

__all__ = [
    "ResearchAgent",
    "StrategyAgent",
    "ScriptAgent",
    "CreativeAgent",
    "VerificationAgent",
    "AnalyticsAgent",
]
