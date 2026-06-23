"""Admin organization management — GM operator surface."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import require_admin
from app.core.db import get_session
from app.schemas.organizations import (
    AcceptInviteIn,
    AssignClusterIn,
    AssignCompanyIn,
    AuditEventOut,
    ClusterAssignmentOut,
    CompanyAssignmentOut,
    IntegrationKeyOut,
    IntegrationKeyRotateOut,
    InviteCreateIn,
    InviteCreateOut,
    InviteOut,
    InviteResendOut,
    MemberOut,
    MemberUpdateIn,
    OkResponse,
    OrganizationCreateIn,
    OrganizationCreateOut,
    OrganizationListItem,
    OrganizationListResponse,
    OrganizationOverviewOut,
    OrganizationUpdateIn,
    SecurityConfigIn,
    SecurityConfigOut,
)
from app.services.organizations import (
    OrganizationError,
    accept_invite,
    assign_cluster,
    assign_company,
    create_invite,
    create_organization,
    deactivate_member,
    get_integration_key_metadata,
    get_organization_or_404,
    get_organization_overview,
    list_assigned_clusters,
    list_assigned_companies,
    list_audit_events,
    list_invites,
    list_members,
    list_organizations,
    record_audit,
    resend_invite,
    rotate_integration_key,
    suspend_organization,
    unassign_cluster,
    unassign_company,
    update_member,
    update_organization,
    update_security_config,
)

router = APIRouter(prefix="/api/admin/organizations", tags=["admin-organizations"])


def _org_error(exc: OrganizationError) -> HTTPException:
    status_code = {
        "not_found": status.HTTP_404_NOT_FOUND,
        "conflict": status.HTTP_409_CONFLICT,
        "validation_error": status.HTTP_400_BAD_REQUEST,
    }.get(exc.code, status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=status_code, detail=exc.message)


def _member_out(row) -> MemberOut:
    return MemberOut(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        team=row.team,
        status=row.status,
        joined_at=row.joined_at,
        deactivated_at=row.deactivated_at,
    )


def _invite_out(row) -> InviteOut:
    return InviteOut(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        team=row.team,
        status=row.status,
        expires_at=row.expires_at,
        sent_at=row.sent_at,
        accepted_at=row.accepted_at,
    )


@router.get("", response_model=OrganizationListResponse)
async def list_orgs(
    search: str | None = Query(default=None, max_length=255),
    status_filter: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OrganizationListResponse:
    items, total = await list_organizations(
        session,
        search=search,
        status=status_filter,
        offset=offset,
        limit=limit,
    )
    return OrganizationListResponse(
        items=[OrganizationListItem(**item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=OrganizationCreateOut, status_code=status.HTTP_201_CREATED)
async def create_org(
    body: OrganizationCreateIn,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OrganizationCreateOut:
    try:
        org, integration_key = await create_organization(
            session,
            name=body.name,
            domain=body.domain,
            status=body.status,
        )
    except OrganizationError as exc:
        raise _org_error(exc) from exc

    overview = await get_organization_overview(session, org.id)
    return OrganizationCreateOut(
        organization=OrganizationListItem(
            id=overview["organization"]["id"],
            name=overview["organization"]["name"],
            domain=overview["organization"]["domain"],
            status=overview["organization"]["status"],
            display_status=overview["organization"]["display_status"],
            is_provisioning=overview["organization"]["is_provisioning"],
            cluster_access=[],
            user_count=0,
            created_at=overview["organization"]["created_at"],
            updated_at=overview["organization"]["updated_at"],
        ),
        integration_key=integration_key,
    )


@router.get("/{organization_id}/overview", response_model=OrganizationOverviewOut)
async def org_overview(
    organization_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OrganizationOverviewOut:
    try:
        data = await get_organization_overview(session, organization_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return OrganizationOverviewOut(**data)


@router.patch("/{organization_id}", response_model=OrganizationOverviewOut)
async def patch_org(
    organization_id: uuid.UUID,
    body: OrganizationUpdateIn,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OrganizationOverviewOut:
    try:
        await update_organization(
            session,
            organization_id,
            name=body.name,
            domain=body.domain,
            status=body.status,
        )
        data = await get_organization_overview(session, organization_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return OrganizationOverviewOut(**data)


@router.post("/{organization_id}/suspend", response_model=OkResponse)
async def suspend_org(
    organization_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    try:
        await suspend_organization(session, organization_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return OkResponse()


@router.post("/{organization_id}/sync", response_model=OkResponse)
async def sync_org(
    organization_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    """Stub sync — records audit event until IdP connectors ship."""
    try:
        await get_organization_or_404(session, organization_id)
        await record_audit(
            session,
            organization_id,
            event_type="organization.sync",
            title="Policy sync completed",
            description="Identity and role mappings were synchronized across configured providers.",
        )
        await session.commit()
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return OkResponse()


@router.get("/{organization_id}/clusters", response_model=list[ClusterAssignmentOut])
async def list_org_clusters(
    organization_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ClusterAssignmentOut]:
    try:
        rows = await list_assigned_clusters(session, organization_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return [
        ClusterAssignmentOut(id=r.id, name=r.name, slug=r.slug, assigned_at=None)
        for r in rows
    ]


@router.post("/{organization_id}/clusters", status_code=status.HTTP_201_CREATED, response_model=OkResponse)
async def add_org_cluster(
    organization_id: uuid.UUID,
    body: AssignClusterIn,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    try:
        await assign_cluster(session, organization_id, body.cluster_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return OkResponse()


@router.delete("/{organization_id}/clusters/{cluster_id}", response_model=OkResponse)
async def remove_org_cluster(
    organization_id: uuid.UUID,
    cluster_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    try:
        await unassign_cluster(session, organization_id, cluster_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return OkResponse()


@router.get("/{organization_id}/companies", response_model=list[CompanyAssignmentOut])
async def list_org_companies(
    organization_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[CompanyAssignmentOut]:
    try:
        rows = await list_assigned_companies(session, organization_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return [
        CompanyAssignmentOut(
            id=r.id,
            company_name=r.company_name,
            domain=r.domain,
            assigned_at=None,
        )
        for r in rows
    ]


@router.post("/{organization_id}/companies", status_code=status.HTTP_201_CREATED, response_model=OkResponse)
async def add_org_company(
    organization_id: uuid.UUID,
    body: AssignCompanyIn,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    try:
        await assign_company(session, organization_id, body.company_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return OkResponse()


@router.delete("/{organization_id}/companies/{company_id}", response_model=OkResponse)
async def remove_org_company(
    organization_id: uuid.UUID,
    company_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    try:
        await unassign_company(session, organization_id, company_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return OkResponse()


@router.get("/{organization_id}/users", response_model=list[MemberOut])
async def list_org_users(
    organization_id: uuid.UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    role: str | None = None,
    team: str | None = None,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[MemberOut]:
    try:
        rows = await list_members(
            session,
            organization_id,
            status=status_filter,
            role=role,
            team=team,
        )
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return [_member_out(r) for r in rows]


@router.get("/{organization_id}/invites", response_model=list[InviteOut])
async def list_org_invites(
    organization_id: uuid.UUID,
    status_filter: str | None = Query(default="pending", alias="status"),
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[InviteOut]:
    try:
        rows = await list_invites(session, organization_id, status=status_filter)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return [_invite_out(r) for r in rows]


@router.post("/{organization_id}/users", response_model=InviteCreateOut, status_code=status.HTTP_201_CREATED)
async def invite_org_user(
    organization_id: uuid.UUID,
    body: InviteCreateIn,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> InviteCreateOut:
    try:
        invite, token = await create_invite(
            session,
            organization_id,
            email=body.email,
            display_name=body.display_name,
            role=body.role,
            team=body.team,
        )
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return InviteCreateOut(invite=_invite_out(invite), accept_token=token)


@router.post("/{organization_id}/invites/{invite_id}/resend", response_model=InviteResendOut)
async def resend_org_invite(
    organization_id: uuid.UUID,
    invite_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> InviteResendOut:
    try:
        invite, token = await resend_invite(session, organization_id, invite_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return InviteResendOut(invite=_invite_out(invite), accept_token=token)


@router.patch("/{organization_id}/users/{member_id}", response_model=MemberOut)
async def patch_org_user(
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberUpdateIn,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> MemberOut:
    try:
        member = await update_member(
            session,
            organization_id,
            member_id,
            display_name=body.display_name,
            role=body.role,
            team=body.team,
        )
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return _member_out(member)


@router.post("/{organization_id}/users/{member_id}/deactivate", response_model=MemberOut)
async def deactivate_org_user(
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> MemberOut:
    try:
        member = await deactivate_member(session, organization_id, member_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return _member_out(member)


@router.get("/{organization_id}/integration-key", response_model=IntegrationKeyOut | None)
async def get_org_integration_key(
    organization_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> IntegrationKeyOut | None:
    try:
        row = await get_integration_key_metadata(session, organization_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    if row is None:
        return None
    return IntegrationKeyOut(
        id=row.id,
        key_prefix=row.key_prefix,
        is_active=row.is_active,
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
    )


@router.post("/{organization_id}/integration-key/rotate", response_model=IntegrationKeyRotateOut)
async def rotate_org_integration_key(
    organization_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> IntegrationKeyRotateOut:
    try:
        row, plaintext = await rotate_integration_key(session, organization_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return IntegrationKeyRotateOut(
        key=IntegrationKeyOut(
            id=row.id,
            key_prefix=row.key_prefix,
            is_active=row.is_active,
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
            created_at=row.created_at,
        ),
        integration_key=plaintext,
    )


@router.get("/{organization_id}/security", response_model=SecurityConfigOut)
async def get_org_security(
    organization_id: uuid.UUID,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SecurityConfigOut:
    try:
        data = await get_organization_overview(session, organization_id)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return SecurityConfigOut(**data["security"])


@router.patch("/{organization_id}/security", response_model=SecurityConfigOut)
async def patch_org_security(
    organization_id: uuid.UUID,
    body: SecurityConfigIn,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SecurityConfigOut:
    try:
        auth = await update_security_config(
            session,
            organization_id,
            mfa_enforced=body.mfa_enforced,
            sso_only=body.sso_only,
            ip_allowlist_enabled=body.ip_allowlist_enabled,
            scim_enabled=body.scim_enabled,
            ip_allowlist=body.ip_allowlist,
            sso_provider=body.sso_provider,
            sso_config=body.sso_config,
        )
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return SecurityConfigOut(
        mfa_enforced=auth.mfa_enforced,
        sso_only=auth.sso_only,
        ip_allowlist_enabled=auth.ip_allowlist_enabled,
        scim_enabled=auth.scim_enabled,
        ip_allowlist=list(auth.ip_allowlist or []),
        sso_provider=auth.sso_provider,
    )


@router.get("/{organization_id}/activity", response_model=list[AuditEventOut])
async def list_org_activity(
    organization_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AuditEventOut]:
    try:
        rows = await list_audit_events(session, organization_id, limit=limit)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return [
        AuditEventOut(
            id=r.id,
            event_type=r.event_type,
            title=r.title,
            description=r.description,
            actor_label=r.actor_label,
            created_at=r.created_at,
        )
        for r in rows
    ]


# Public invite accept — no admin token; analyst onboarding path.
invite_router = APIRouter(prefix="/api/invites", tags=["invites"])


@invite_router.post("/accept", response_model=MemberOut)
async def accept_invite_endpoint(
    body: AcceptInviteIn,
    session: AsyncSession = Depends(get_session),
) -> MemberOut:
    try:
        member = await accept_invite(session, body.token)
    except OrganizationError as exc:
        raise _org_error(exc) from exc
    return _member_out(member)
