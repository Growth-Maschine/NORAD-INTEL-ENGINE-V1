"""SQLAlchemy ORM models for NORAD.

Importing this package registers every model on `Base.metadata` — needed by
Alembic to autogenerate / verify migrations.

Core (rev 0001):
- `runs`      : a research run kicked off by a user (or later, by a bot)
- `companies` : the canonical company record (one per company)
- `cards`     : the full `CompanyCardV1` JSON, one row per research output
- `signals`   : denormalized signals for fast timeline/filtering
- `sources`   : denormalized sources for fast attribution lookup

Discovery + observability (rev 0002):
- `trend_articles` : one row per article surfaced by a discovery funnel
- `run_events`     : append-only timeline of events per run (drives SSE)
- `engine_calls`   : per-call cost + latency audit log
"""
from app.models.app_kv import AppKV
from app.models.card import Card
from app.models.company import Company
from app.models.engine_call import EngineCall
from app.models.run import Run
from app.models.run_event import RunEvent
from app.models.signal import Signal
from app.models.source import Source
from app.models.trend_article import TrendArticle

__all__ = [
    "AppKV",
    "Card",
    "Company",
    "EngineCall",
    "Run",
    "RunEvent",
    "Signal",
    "Source",
    "TrendArticle",
]
