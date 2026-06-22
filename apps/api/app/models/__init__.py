"""SQLAlchemy ORM models for NORAD.

Importing this package registers every model on `Base.metadata`.

Core:
- `runs`, `companies`, `cards`, `card_profile_parameters`, `sources`

Observability:
- `run_events`, `engine_calls`, `app_kv`

Web Discovery:
- `web_discovery_clusters`, `web_discovery_queries`, `articles`
"""
from app.models.app_kv import AppKV
from app.models.article import Article
from app.models.card import Card
from app.models.card_profile_parameter import CardProfileParameter
from app.models.company import Company
from app.models.engine_call import EngineCall
from app.models.run import Run
from app.models.run_event import RunEvent
from app.models.source import Source
from app.models.web_discovery_cluster import WebDiscoveryCluster
from app.models.web_discovery_query import WebDiscoveryQuery

__all__ = [
    "AppKV",
    "Article",
    "Card",
    "CardProfileParameter",
    "Company",
    "EngineCall",
    "Run",
    "RunEvent",
    "Source",
    "WebDiscoveryCluster",
    "WebDiscoveryQuery",
]
