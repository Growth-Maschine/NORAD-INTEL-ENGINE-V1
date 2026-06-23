"""Pydantic contracts for admin organization APIs."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OrgStatus = Literal["active", "suspended"]
DisplayStatus = Literal["active", "suspended", "provisioning"]
MemberRole = Literal["staff", "manager"]
MemberStatus = Literal["active", "deactivated"]
InviteStatus = Literal["pending", "accepted", "expired", "cancelled"]


class ClusterAccessRef(BaseModel):
    slug: str
    name: str


class OrganizationListItem(BaseModel):
    id: uuid.UUID
    name: str
    domain: str
    status: OrgStatus
    display_status: DisplayStatus
    is_provisioning: bool
    cluster_access: list[ClusterAccessRef]
    user_count: int
    created_at: datetime
    updated_at: datetime


class OrganizationListResponse(BaseModel):
    items: list[OrganizationListItem]
    total: int
    offset: int
    limit: int


class OrganizationCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=255)
    status: OrgStatus = "active"


class OrganizationCreateOut(BaseModel):
    organization: OrganizationListItem
    integration_key: str = Field(
        ...,
        description="Plaintext integration key — shown once; store securely.",
    )


class OrganizationUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, min_length=1, max_length=255)
    status: OrgStatus | None = None


class OrganizationRef(BaseModel):
    id: uuid.UUID
    name: str
    domain: str
    status: OrgStatus
    display_status: DisplayStatus
    is_provisioning: bool
    created_at: datetime
    updated_at: datetime


class OverviewMetrics(BaseModel):
    total_users: int
    active_users: int
    pending_invites: int
    privileged_access: int
    scope_mapped: int
    cluster_count: int
    company_count: int
    security_score: int


class OperationalHealth(BaseModel):
    identity_posture: str
    mfa_enforced: bool
    user_coverage: str
    cluster_assignment: str
    company_mapping: str


class SecurityConfigOut(BaseModel):
    mfa_enforced: bool
    sso_only: bool
    ip_allowlist_enabled: bool
    scim_enabled: bool
    ip_allowlist: list[str]
    sso_provider: str | None


class OrganizationOverviewOut(BaseModel):
    organization: OrganizationRef
    metrics: OverviewMetrics
    operational_health: OperationalHealth
    security: SecurityConfigOut


class SecurityConfigIn(BaseModel):
    mfa_enforced: bool | None = None
    sso_only: bool | None = None
    ip_allowlist_enabled: bool | None = None
    scim_enabled: bool | None = None
    ip_allowlist: list[str] | None = None
    sso_provider: str | None = Field(default=None, max_length=64)
    sso_config: dict[str, Any] | None = None


class ClusterAssignmentOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    assigned_at: datetime | None = None


class CompanyAssignmentOut(BaseModel):
    id: uuid.UUID
    company_name: str
    domain: str | None
    assigned_at: datetime | None = None


class AssignClusterIn(BaseModel):
    cluster_id: uuid.UUID


class AssignCompanyIn(BaseModel):
    company_id: uuid.UUID


class MemberOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: MemberRole
    team: str | None
    status: MemberStatus
    joined_at: datetime
    deactivated_at: datetime | None = None


class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: MemberRole
    team: str | None
    status: InviteStatus
    expires_at: datetime
    sent_at: datetime | None
    accepted_at: datetime | None


class InviteCreateIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    display_name: str = Field(..., min_length=1, max_length=255)
    role: MemberRole = "staff"
    team: str | None = Field(default=None, max_length=120)


class InviteCreateOut(BaseModel):
    invite: InviteOut
    accept_token: str = Field(
        ...,
        description="Plaintext invite token — shown once until email delivery ships.",
    )


class InviteResendOut(BaseModel):
    invite: InviteOut
    accept_token: str


class MemberUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: MemberRole | None = None
    team: str | None = Field(default=None, max_length=120)


class IntegrationKeyOut(BaseModel):
    id: uuid.UUID
    key_prefix: str
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class IntegrationKeyRotateOut(BaseModel):
    key: IntegrationKeyOut
    integration_key: str = Field(
        ...,
        description="Plaintext integration key — shown once after rotation.",
    )


class AuditEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    title: str
    description: str | None
    actor_label: str | None
    created_at: datetime


class AcceptInviteIn(BaseModel):
    token: str = Field(..., min_length=16)


class OkResponse(BaseModel):
    ok: bool = True
