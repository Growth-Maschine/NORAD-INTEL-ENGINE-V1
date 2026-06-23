"""SQLAlchemy ORM models for NORAD.

Importing this package registers every model on `Base.metadata`.

Core:
- `runs`, `companies`, `cards`, `card_profile_parameters`, `sources`

Observability:
- `run_events`, `engine_calls`, `app_kv`

Web Discovery:
- `web_discovery_clusters`, `web_discovery_queries`, `articles`

Organizations (multi-tenant admin):
- `organizations`, `organization_members`, `organization_invites`
- `organization_api_keys`, `organization_clusters`, `organization_companies`
- `organization_auth_config`, `organization_audit_events`
"""
from app.models.app_kv import AppKV
from app.models.article import Article
from app.models.card import Card
from app.models.card_profile_parameter import CardProfileParameter
from app.models.company import Company
from app.models.engine_call import EngineCall
from app.models.organization import Organization
from app.models.organization_api_key import OrganizationApiKey
from app.models.organization_audit_event import OrganizationAuditEvent
from app.models.organization_auth_config import OrganizationAuthConfig
from app.models.organization_cluster import OrganizationCluster
from app.models.organization_company import OrganizationCompany
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
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
    "Organization",
    "OrganizationApiKey",
    "OrganizationAuditEvent",
    "OrganizationAuthConfig",
    "OrganizationCluster",
    "OrganizationCompany",
    "OrganizationInvite",
    "OrganizationMember",
    "Run",
    "RunEvent",
    "Source",
    "WebDiscoveryCluster",
    "WebDiscoveryQuery",
]
