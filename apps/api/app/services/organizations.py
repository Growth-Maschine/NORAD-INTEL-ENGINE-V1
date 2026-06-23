"""Organization service layer — tenant CRUD, access scoping, invites, overview."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.organization import (
    ACTIVE_RUN_STATUSES,
    INVITE_STATUSES,
    MEMBER_ROLES,
    MEMBER_STATUSES,
    ORGANIZATION_STATUSES,
    Organization,
)
from app.models.organization_api_key import OrganizationApiKey
from app.models.organization_audit_event import OrganizationAuditEvent
from app.models.organization_auth_config import OrganizationAuthConfig
from app.models.organization_cluster import OrganizationCluster
from app.models.organization_company import OrganizationCompany
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.models.run import Run
from app.models.web_discovery_cluster import WebDiscoveryCluster
from app.services.org_credentials import (
    generate_integration_key,
    generate_invite_token,
    hash_secret,
)
from app.services.org_normalization import normalize_domain, normalize_email

INVITE_TTL_DAYS = 7
PRIVILEGED_ROLES = frozenset({"manager"})


class OrganizationError(Exception):
    def __init__(self, message: str, *, code: str = "organization_error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def record_audit(
    session: AsyncSession,
    organization_id: uuid.UUID,
    *,
    event_type: str,
    title: str,
    description: str | None = None,
    actor_label: str = "admin",
    metadata: dict[str, Any] | None = None,
) -> OrganizationAuditEvent:
    row = OrganizationAuditEvent(
        organization_id=organization_id,
        event_type=event_type,
        title=title,
        description=description,
        actor_label=actor_label,
        metadata_=metadata or {},
    )
    session.add(row)
    return row


async def get_organization_or_404(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> Organization:
    org = await session.get(Organization, organization_id)
    if org is None:
        raise OrganizationError("organization not found", code="not_found")
    return org


async def org_cluster_ids(session: AsyncSession, organization_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        await session.execute(
            select(OrganizationCluster.cluster_id).where(
                OrganizationCluster.organization_id == organization_id
            )
        )
    ).scalars().all()
    return list(rows)


async def org_company_ids(session: AsyncSession, organization_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        await session.execute(
            select(OrganizationCompany.company_id).where(
                OrganizationCompany.organization_id == organization_id
            )
        )
    ).scalars().all()
    return list(rows)


async def is_org_provisioning(session: AsyncSession, organization_id: uuid.UUID) -> bool:
    """True when discovery or research runs are in-flight for this org's scope."""
    cluster_ids = await org_cluster_ids(session, organization_id)
    company_ids = await org_company_ids(session, organization_id)
    if not cluster_ids and not company_ids:
        return False

    clauses = []
    if cluster_ids:
        for cid in cluster_ids:
            clauses.append(Run.engines["cluster_id"].astext == str(cid))
    if company_ids:
        clauses.append(Run.company_id.in_(company_ids))

    stmt = select(func.count()).select_from(Run).where(
        Run.status.in_(ACTIVE_RUN_STATUSES),
        or_(*clauses),
    )
    count = (await session.execute(stmt)).scalar_one()
    return count > 0


def compute_security_score(auth: OrganizationAuthConfig, *, provisioning: bool) -> int:
    if provisioning:
        return 78
    score = 50
    if auth.mfa_enforced:
        score += 15
    if auth.sso_only:
        score += 10
    if auth.scim_enabled:
        score += 10
    if auth.ip_allowlist_enabled:
        score += 15
    return min(score, 100)


async def create_organization(
    session: AsyncSession,
    *,
    name: str,
    domain: str,
    status: str = "active",
) -> tuple[Organization, str]:
    """Create org with default auth config and integration key. Returns org + plaintext key."""
    if status not in ORGANIZATION_STATUSES:
        raise OrganizationError("invalid status", code="validation_error")

    clean_name = name.strip()
    if not clean_name:
        raise OrganizationError("name is required", code="validation_error")

    try:
        clean_domain = normalize_domain(domain)
    except ValueError as exc:
        raise OrganizationError(str(exc), code="validation_error") from exc

    org = Organization(name=clean_name, domain=clean_domain, status=status)
    session.add(org)
    await session.flush()

    session.add(OrganizationAuthConfig(organization_id=org.id))

    full_key, key_prefix, key_hash = generate_integration_key()
    session.add(
        OrganizationApiKey(
            organization_id=org.id,
            key_prefix=key_prefix,
            key_hash=key_hash,
        )
    )

    await record_audit(
        session,
        org.id,
        event_type="organization.created",
        title="Organization created",
        description=f"{clean_name} ({clean_domain}) was created.",
    )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise OrganizationError(
            "domain already in use",
            code="conflict",
        ) from exc

    await session.refresh(org)
    return org, full_key


async def list_organizations(
    session: AsyncSession,
    *,
    search: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(Organization)
    count_stmt = select(func.count()).select_from(Organization)

    if status and status in ORGANIZATION_STATUSES:
        stmt = stmt.where(Organization.status == status)
        count_stmt = count_stmt.where(Organization.status == status)

    if search:
        term = f"%{search.strip()}%"
        filt = or_(Organization.name.ilike(term), Organization.domain.ilike(term))
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)

    total = (await session.execute(count_stmt)).scalar_one()
    orgs = (
        await session.execute(
            stmt.order_by(Organization.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    items: list[dict[str, Any]] = []
    for org in orgs:
        items.append(await _organization_list_item(session, org))

    return items, total


async def _organization_list_item(session: AsyncSession, org: Organization) -> dict[str, Any]:
    cluster_rows = (
        await session.execute(
            select(WebDiscoveryCluster.slug, WebDiscoveryCluster.name)
            .join(
                OrganizationCluster,
                OrganizationCluster.cluster_id == WebDiscoveryCluster.id,
            )
            .where(OrganizationCluster.organization_id == org.id)
            .order_by(WebDiscoveryCluster.name)
        )
    ).all()

    user_count = (
        await session.execute(
            select(func.count())
            .select_from(OrganizationMember)
            .where(OrganizationMember.organization_id == org.id)
        )
    ).scalar_one()

    provisioning = await is_org_provisioning(session, org.id)
    display_status = "provisioning" if provisioning and org.status == "active" else org.status

    return {
        "id": org.id,
        "name": org.name,
        "domain": org.domain,
        "status": org.status,
        "display_status": display_status,
        "is_provisioning": provisioning,
        "cluster_access": [{"slug": slug, "name": name} for slug, name in cluster_rows],
        "user_count": user_count,
        "created_at": org.created_at,
        "updated_at": org.updated_at,
    }


async def get_organization_overview(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> dict[str, Any]:
    org = await get_organization_or_404(session, organization_id)
    auth = await session.get(OrganizationAuthConfig, organization_id)
    if auth is None:
        auth = OrganizationAuthConfig(organization_id=organization_id)
        session.add(auth)
        await session.flush()

    total_users = (
        await session.execute(
            select(func.count())
            .select_from(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
        )
    ).scalar_one()

    active_users = (
        await session.execute(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.status == "active",
            )
        )
    ).scalar_one()

    pending_invites = (
        await session.execute(
            select(func.count())
            .select_from(OrganizationInvite)
            .where(
                OrganizationInvite.organization_id == organization_id,
                OrganizationInvite.status == "pending",
                OrganizationInvite.expires_at > _utcnow(),
            )
        )
    ).scalar_one()

    privileged_access = (
        await session.execute(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role.in_(tuple(PRIVILEGED_ROLES)),
                OrganizationMember.status == "active",
            )
        )
    ).scalar_one()

    cluster_count = (
        await session.execute(
            select(func.count())
            .select_from(OrganizationCluster)
            .where(OrganizationCluster.organization_id == organization_id)
        )
    ).scalar_one()

    company_count = (
        await session.execute(
            select(func.count())
            .select_from(OrganizationCompany)
            .where(OrganizationCompany.organization_id == organization_id)
        )
    ).scalar_one()

    provisioning = await is_org_provisioning(session, organization_id)
    display_status = "provisioning" if provisioning and org.status == "active" else org.status

    return {
        "organization": {
            "id": org.id,
            "name": org.name,
            "domain": org.domain,
            "status": org.status,
            "display_status": display_status,
            "is_provisioning": provisioning,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
        },
        "metrics": {
            "total_users": total_users,
            "active_users": active_users,
            "pending_invites": pending_invites,
            "privileged_access": privileged_access,
            "scope_mapped": cluster_count + company_count,
            "cluster_count": cluster_count,
            "company_count": company_count,
            "security_score": compute_security_score(auth, provisioning=provisioning),
        },
        "operational_health": {
            "identity_posture": "MFA enforced" if auth.mfa_enforced else "MFA not enforced",
            "mfa_enforced": auth.mfa_enforced,
            "user_coverage": f"{active_users}/{total_users} users active",
            "cluster_assignment": f"{cluster_count} clusters available",
            "company_mapping": f"{company_count} companies attached",
        },
        "security": {
            "mfa_enforced": auth.mfa_enforced,
            "sso_only": auth.sso_only,
            "ip_allowlist_enabled": auth.ip_allowlist_enabled,
            "scim_enabled": auth.scim_enabled,
            "ip_allowlist": list(auth.ip_allowlist or []),
            "sso_provider": auth.sso_provider,
        },
    }


async def update_organization(
    session: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str | None = None,
    domain: str | None = None,
    status: str | None = None,
) -> Organization:
    org = await get_organization_or_404(session, organization_id)

    if name is not None:
        clean = name.strip()
        if not clean:
            raise OrganizationError("name is required", code="validation_error")
        org.name = clean

    if domain is not None:
        try:
            org.domain = normalize_domain(domain)
        except ValueError as exc:
            raise OrganizationError(str(exc), code="validation_error") from exc

    if status is not None:
        if status not in ORGANIZATION_STATUSES:
            raise OrganizationError("invalid status", code="validation_error")
        org.status = status

    await record_audit(
        session,
        organization_id,
        event_type="organization.updated",
        title="Organization profile updated",
        description=f"Profile for {org.name} was updated.",
    )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise OrganizationError("domain already in use", code="conflict") from exc

    await session.refresh(org)
    return org


async def suspend_organization(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> Organization:
    org = await get_organization_or_404(session, organization_id)
    org.status = "suspended"
    await record_audit(
        session,
        organization_id,
        event_type="organization.suspended",
        title="Organization suspended",
        description=f"{org.name} was suspended by an administrator.",
    )
    await session.commit()
    await session.refresh(org)
    return org


async def assign_cluster(
    session: AsyncSession,
    organization_id: uuid.UUID,
    cluster_id: uuid.UUID,
) -> None:
    await get_organization_or_404(session, organization_id)
    cluster = await session.get(WebDiscoveryCluster, cluster_id)
    if cluster is None:
        raise OrganizationError("cluster not found", code="not_found")

    existing = await session.get(
        OrganizationCluster,
        {"organization_id": organization_id, "cluster_id": cluster_id},
    )
    if existing is not None:
        return

    session.add(
        OrganizationCluster(organization_id=organization_id, cluster_id=cluster_id)
    )
    await record_audit(
        session,
        organization_id,
        event_type="access.cluster_assigned",
        title="Cluster access granted",
        description=f"Cluster {cluster.slug} was assigned to the organization.",
    )
    await session.commit()


async def unassign_cluster(
    session: AsyncSession,
    organization_id: uuid.UUID,
    cluster_id: uuid.UUID,
) -> None:
    row = await session.get(
        OrganizationCluster,
        {"organization_id": organization_id, "cluster_id": cluster_id},
    )
    if row is None:
        raise OrganizationError("cluster assignment not found", code="not_found")
    await session.delete(row)
    await record_audit(
        session,
        organization_id,
        event_type="access.cluster_removed",
        title="Cluster access removed",
        description="A cluster was removed from the organization scope.",
    )
    await session.commit()


async def assign_company(
    session: AsyncSession,
    organization_id: uuid.UUID,
    company_id: uuid.UUID,
) -> None:
    await get_organization_or_404(session, organization_id)
    company = await session.get(Company, company_id)
    if company is None:
        raise OrganizationError("company not found", code="not_found")

    existing = (
        await session.execute(
            select(OrganizationCompany).where(OrganizationCompany.company_id == company_id)
        )
    ).scalar_one_or_none()
    if existing is not None and existing.organization_id != organization_id:
        raise OrganizationError(
            "company is already assigned to another organization",
            code="conflict",
        )
    if existing is not None:
        return

    session.add(
        OrganizationCompany(organization_id=organization_id, company_id=company_id)
    )
    await record_audit(
        session,
        organization_id,
        event_type="access.company_assigned",
        title="Company attached",
        description=f"Company {company.company_name} was attached to the organization.",
        metadata={"company_id": str(company_id)},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise OrganizationError(
            "company is already assigned to another organization",
            code="conflict",
        ) from exc


async def unassign_company(
    session: AsyncSession,
    organization_id: uuid.UUID,
    company_id: uuid.UUID,
) -> None:
    row = await session.get(
        OrganizationCompany,
        {"organization_id": organization_id, "company_id": company_id},
    )
    if row is None:
        raise OrganizationError("company assignment not found", code="not_found")
    await session.delete(row)
    await record_audit(
        session,
        organization_id,
        event_type="access.company_removed",
        title="Company detached",
        description="A company was removed from the organization scope.",
    )
    await session.commit()


async def create_invite(
    session: AsyncSession,
    organization_id: uuid.UUID,
    *,
    email: str,
    display_name: str,
    role: str = "staff",
    team: str | None = None,
) -> tuple[OrganizationInvite, str]:
    await get_organization_or_404(session, organization_id)

    if role not in MEMBER_ROLES:
        raise OrganizationError("invalid role", code="validation_error")

    try:
        clean_email = normalize_email(email)
    except ValueError as exc:
        raise OrganizationError(str(exc), code="validation_error") from exc

    clean_name = display_name.strip()
    if not clean_name:
        raise OrganizationError("display_name is required", code="validation_error")

    member = (
        await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.email == clean_email,
            )
        )
    ).scalar_one_or_none()
    if member is not None:
        raise OrganizationError("user already exists in organization", code="conflict")

    pending = (
        await session.execute(
            select(OrganizationInvite).where(
                OrganizationInvite.organization_id == organization_id,
                OrganizationInvite.email == clean_email,
                OrganizationInvite.status == "pending",
                OrganizationInvite.expires_at > _utcnow(),
            )
        )
    ).scalar_one_or_none()
    if pending is not None:
        raise OrganizationError("pending invite already exists for this email", code="conflict")

    token, token_hash = generate_invite_token()
    now = _utcnow()
    invite = OrganizationInvite(
        organization_id=organization_id,
        email=clean_email,
        display_name=clean_name,
        role=role,
        team=(team.strip() if team else None) or None,
        status="pending",
        token_hash=token_hash,
        expires_at=now + timedelta(days=INVITE_TTL_DAYS),
        sent_at=now,
    )
    session.add(invite)
    await record_audit(
        session,
        organization_id,
        event_type="user.invited",
        title="User invited",
        description=f"Invitation sent to {clean_email}.",
        metadata={"email": clean_email, "role": role},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise OrganizationError("invite could not be created", code="conflict") from exc

    await session.refresh(invite)
    return invite, token


async def resend_invite(
    session: AsyncSession,
    organization_id: uuid.UUID,
    invite_id: uuid.UUID,
) -> tuple[OrganizationInvite, str]:
    invite = await session.get(OrganizationInvite, invite_id)
    if invite is None or invite.organization_id != organization_id:
        raise OrganizationError("invite not found", code="not_found")
    if invite.status != "pending":
        raise OrganizationError("invite is not pending", code="validation_error")

    token, token_hash = generate_invite_token()
    now = _utcnow()
    invite.token_hash = token_hash
    invite.expires_at = now + timedelta(days=INVITE_TTL_DAYS)
    invite.sent_at = now

    await record_audit(
        session,
        organization_id,
        event_type="user.invite_resent",
        title="Invitation resent",
        description=f"Invitation resent to {invite.email}.",
    )
    await session.commit()
    await session.refresh(invite)
    return invite, token


async def accept_invite(session: AsyncSession, token: str) -> OrganizationMember:
    token_hash = hash_secret(token)

    invite = (
        await session.execute(
            select(OrganizationInvite).where(OrganizationInvite.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if invite is None:
        raise OrganizationError("invalid or expired invite", code="not_found")

    now = _utcnow()
    if invite.status != "pending":
        raise OrganizationError("invite is no longer valid", code="validation_error")
    if invite.expires_at <= now:
        invite.status = "expired"
        await session.commit()
        raise OrganizationError("invite has expired", code="validation_error")

    member = OrganizationMember(
        organization_id=invite.organization_id,
        email=invite.email,
        display_name=invite.display_name,
        role=invite.role,
        team=invite.team,
        status="active",
        joined_at=now,
    )
    invite.status = "accepted"
    invite.accepted_at = now
    session.add(member)

    await record_audit(
        session,
        invite.organization_id,
        event_type="user.invite_accepted",
        title="User joined organization",
        description=f"{invite.email} accepted their invitation.",
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise OrganizationError("user already exists", code="conflict") from exc

    await session.refresh(member)
    return member


async def deactivate_member(
    session: AsyncSession,
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
) -> OrganizationMember:
    member = await session.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise OrganizationError("member not found", code="not_found")

    now = _utcnow()
    member.status = "deactivated"
    member.deactivated_at = now

    await record_audit(
        session,
        organization_id,
        event_type="user.deactivated",
        title="User deactivated",
        description=f"{member.email} was deactivated.",
    )
    await session.commit()
    await session.refresh(member)
    return member


async def update_member(
    session: AsyncSession,
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
    *,
    display_name: str | None = None,
    role: str | None = None,
    team: str | None = None,
) -> OrganizationMember:
    member = await session.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise OrganizationError("member not found", code="not_found")

    if display_name is not None:
        clean = display_name.strip()
        if not clean:
            raise OrganizationError("display_name is required", code="validation_error")
        member.display_name = clean

    if role is not None:
        if role not in MEMBER_ROLES:
            raise OrganizationError("invalid role", code="validation_error")
        member.role = role

    if team is not None:
        member.team = team.strip() or None

    await session.commit()
    await session.refresh(member)
    return member


async def rotate_integration_key(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> tuple[OrganizationApiKey, str]:
    await get_organization_or_404(session, organization_id)
    now = _utcnow()

    active_keys = (
        await session.execute(
            select(OrganizationApiKey).where(
                OrganizationApiKey.organization_id == organization_id,
                OrganizationApiKey.revoked_at.is_(None),
                OrganizationApiKey.is_active.is_(True),
            )
        )
    ).scalars().all()
    for key in active_keys:
        key.is_active = False
        key.revoked_at = now

    full_key, key_prefix, key_hash = generate_integration_key()
    row = OrganizationApiKey(
        organization_id=organization_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
    )
    session.add(row)

    await record_audit(
        session,
        organization_id,
        event_type="integration_key.rotated",
        title="Integration key rotated",
        description="A new integration key was issued for this organization.",
    )
    await session.commit()
    await session.refresh(row)
    return row, full_key


async def get_integration_key_metadata(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> OrganizationApiKey | None:
    return (
        await session.execute(
            select(OrganizationApiKey)
            .where(
                OrganizationApiKey.organization_id == organization_id,
                OrganizationApiKey.revoked_at.is_(None),
                OrganizationApiKey.is_active.is_(True),
            )
            .order_by(OrganizationApiKey.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def update_security_config(
    session: AsyncSession,
    organization_id: uuid.UUID,
    **fields: Any,
) -> OrganizationAuthConfig:
    await get_organization_or_404(session, organization_id)
    auth = await session.get(OrganizationAuthConfig, organization_id)
    if auth is None:
        auth = OrganizationAuthConfig(organization_id=organization_id)
        session.add(auth)
        await session.flush()

    allowed = {
        "mfa_enforced",
        "sso_only",
        "ip_allowlist_enabled",
        "scim_enabled",
        "ip_allowlist",
        "sso_provider",
        "sso_config",
    }
    for key, value in fields.items():
        if key in allowed and value is not None:
            setattr(auth, key, value)

    await record_audit(
        session,
        organization_id,
        event_type="security.policy_updated",
        title="Security policy updated",
        description="Organization security controls were updated.",
    )
    await session.commit()
    await session.refresh(auth)
    return auth


async def list_audit_events(
    session: AsyncSession,
    organization_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[OrganizationAuditEvent]:
    await get_organization_or_404(session, organization_id)
    rows = (
        await session.execute(
            select(OrganizationAuditEvent)
            .where(OrganizationAuditEvent.organization_id == organization_id)
            .order_by(OrganizationAuditEvent.created_at.desc())
            .limit(min(limit, 100))
        )
    ).scalars().all()
    return list(rows)


async def list_members(
    session: AsyncSession,
    organization_id: uuid.UUID,
    *,
    status: str | None = None,
    role: str | None = None,
    team: str | None = None,
) -> list[OrganizationMember]:
    await get_organization_or_404(session, organization_id)
    stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id
    )
    if status and status in MEMBER_STATUSES:
        stmt = stmt.where(OrganizationMember.status == status)
    if role and role in MEMBER_ROLES:
        stmt = stmt.where(OrganizationMember.role == role)
    if team:
        stmt = stmt.where(OrganizationMember.team == team.strip())
    rows = (await session.execute(stmt.order_by(OrganizationMember.joined_at.desc()))).scalars()
    return list(rows)


async def list_invites(
    session: AsyncSession,
    organization_id: uuid.UUID,
    *,
    status: str | None = "pending",
) -> list[OrganizationInvite]:
    await get_organization_or_404(session, organization_id)
    stmt = select(OrganizationInvite).where(
        OrganizationInvite.organization_id == organization_id
    )
    if status and status in INVITE_STATUSES:
        stmt = stmt.where(OrganizationInvite.status == status)
    rows = (await session.execute(stmt.order_by(OrganizationInvite.created_at.desc()))).scalars()
    return list(rows)


async def list_assigned_clusters(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> list[WebDiscoveryCluster]:
    await get_organization_or_404(session, organization_id)
    rows = (
        await session.execute(
            select(WebDiscoveryCluster)
            .join(
                OrganizationCluster,
                OrganizationCluster.cluster_id == WebDiscoveryCluster.id,
            )
            .where(OrganizationCluster.organization_id == organization_id)
            .order_by(WebDiscoveryCluster.name)
        )
    ).scalars().all()
    return list(rows)


async def list_assigned_companies(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> list[Company]:
    await get_organization_or_404(session, organization_id)
    rows = (
        await session.execute(
            select(Company)
            .join(
                OrganizationCompany,
                OrganizationCompany.company_id == Company.id,
            )
            .where(OrganizationCompany.organization_id == organization_id)
            .order_by(Company.company_name)
        )
    ).scalars().all()
    return list(rows)
