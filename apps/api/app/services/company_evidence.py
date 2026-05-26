"""Assemble research evidence for the company detail page.

Reads `engine_calls` for the canonical card's run and normalizes vendor
payloads into a stable JSON shape the frontend can render without parsing
raw engine I/O. This is the "show everything we got" layer — distinct from
the synthesized CompanyCardV1 brief.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Company, EngineCall, Source


def _fmt_diffbot_scalar(v: Any) -> Any:
    if isinstance(v, dict):
        if "str" in v and v["str"]:
            return v["str"]
        if "value" in v:
            return v["value"]
    return v


def _fmt_diffbot_date(v: Any) -> Any:
    s = _fmt_diffbot_scalar(v)
    if isinstance(s, str) and s.startswith("d") and len(s) > 1:
        return s[1:]
    return s


def _fmt_person(p: Any) -> dict[str, Any] | None:
    if not isinstance(p, dict):
        return None
    name = p.get("name") or p.get("fullName")
    if not name:
        return None
    out: dict[str, Any] = {"name": name}
    for k in ("title", "role", "summary", "linkedInUri", "twitterUri", "email"):
        if p.get(k):
            out[k] = p[k]
    return out


def _extract_diffbot_entity(body: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    data = body.get("data") or []
    if not isinstance(data, list) or not data:
        return None
    top = data[0] if isinstance(data[0], dict) else {}
    entity = top.get("entity")
    if not isinstance(entity, dict):
        return None
    score = float(top.get("score") or 0.0)
    return {"entity": entity, "score": score, "hits": body.get("hits", 1)}


def _parse_diffbot(call: EngineCall) -> dict[str, Any] | None:
    payload = call.response_payload
    if not isinstance(payload, dict):
        return None
    extracted = _extract_diffbot_entity(payload)
    if not extracted:
        return None
    e = extracted["entity"]
    meta = call.meta or {}

    founders: list[dict[str, Any]] = []
    for f in e.get("founders") or []:
        p = _fmt_person(f)
        if p:
            founders.append(p)

    executives: list[dict[str, Any]] = []
    for x in e.get("executives") or e.get("boardMembers") or []:
        p = _fmt_person(x)
        if p:
            executives.append(p)

    ceo = _fmt_person(e.get("ceo")) if e.get("ceo") else None

    investments: list[dict[str, Any]] = []
    for inv in e.get("investments") or []:
        if not isinstance(inv, dict):
            continue
        investments.append({
                    "date": _fmt_diffbot_date(inv.get("date")),
            "amount_usd": _fmt_diffbot_scalar(inv.get("amount")),
            "series": inv.get("series") or inv.get("type"),
            "investors": [
                i.get("name") if isinstance(i, dict) else i
                for i in (inv.get("investors") or [])
                if i
            ],
        })

    competitors: list[str] = []
    for c in e.get("competitors") or []:
        if isinstance(c, dict) and c.get("name"):
            competitors.append(str(c["name"]))
        elif isinstance(c, str):
            competitors.append(c)

    industries: list[str] = []
    for i in e.get("industries") or []:
        if isinstance(i, dict) and i.get("name"):
            industries.append(str(i["name"]))
        elif isinstance(i, str):
            industries.append(i)

    categories: list[str] = []
    for c in e.get("categories") or []:
        if isinstance(c, dict) and c.get("name"):
            categories.append(str(c["name"]))
        elif isinstance(c, str):
            categories.append(c)

    origins: list[str] = []
    seen: set[str] = set()
    for key in ("origins", "allUris"):
        for u in e.get(key) or []:
            if isinstance(u, str) and u.startswith("http") and u not in seen:
                seen.add(u)
                origins.append(u)
    for u in (e.get("origin"), e.get("homepageUri")):
        if isinstance(u, str) and u.startswith("http") and u not in seen:
            seen.add(u)
            origins.append(u)

    links: list[dict[str, str]] = []
    for label, key in (
        ("Homepage", "homepageUri"),
        ("LinkedIn", "linkedInUri"),
        ("Crunchbase", "crunchbaseUri"),
        ("Wikipedia", "wikipediaUri"),
        ("Facebook", "facebookUri"),
        ("Twitter", "twitterUri"),
        ("Instagram", "instagramUri"),
    ):
        val = e.get(key)
        if isinstance(val, str) and val.startswith("http"):
            links.append({"label": label, "url": val})

    addr = e.get("address")
    hq = None
    if isinstance(addr, dict):
        parts = [
            addr.get("street"),
            addr.get("city"),
            addr.get("region") or addr.get("regionName"),
            addr.get("country") or addr.get("countryName"),
        ]
        hq = ", ".join(p for p in parts if p)
    elif isinstance(e.get("location"), dict):
        hq = e["location"].get("address")

    return {
        "status": call.status,
        "score": meta.get("score", extracted["score"]),
        "hits": meta.get("hits", extracted["hits"]),
        "latency_ms": call.latency_ms,
        "identity": {
            "name": e.get("name") or e.get("fullName"),
            "aka": e.get("nameAlt"),
            "description": (e.get("description") or "")[:4000] or None,
            "homepage": e.get("homepageUri"),
            "hq": hq,
            "founded": _fmt_diffbot_date(e.get("foundingDate")),
            "is_public": e.get("isPublic"),
            "stock": _fmt_diffbot_scalar(e.get("stock")),
        },
        "people": {
            "ceo": ceo,
            "founders": founders,
            "executives": executives,
        },
        "traction": {
            "employees": _fmt_diffbot_scalar(e.get("nbEmployees"))
            or e.get("nbEmployeesMax")
            or e.get("nbEmployeesMin"),
        },
        "finance": {
            "investments": investments,
            "investment_count": len(investments),
        },
        "market": {
            "industries": industries,
            "categories": categories,
            "competitors": competitors,
        },
        "links": links,
        "origins": origins,
        "field_count": len(e.keys()),
    }


def _unwrap_parallel_output(output: dict[str, Any]) -> tuple[dict[str, Any], list[Any]]:
    """Parallel Task API v2 wraps the schema in `{type, basis, content}`."""
    content = output.get("content")
    basis = output.get("basis") or []
    if isinstance(content, dict):
        return content, basis if isinstance(basis, list) else []
    return output, basis if isinstance(basis, list) else []


def _parse_parallel(call: EngineCall) -> dict[str, Any] | None:
    payload = call.response_payload
    if not isinstance(payload, dict):
        return None
    raw = payload.get("output_json")
    if not isinstance(raw, dict):
        return None
    brief, basis = _unwrap_parallel_output(raw)
    signals = brief.get("signals") or []
    sources = brief.get("sources") or []
    return {
        "status": call.status,
        "processor": call.processor,
        "latency_ms": call.latency_ms,
        "cost_usd": call.cost_usd,
        "brief": brief,
        "basis": basis,
        "citations": payload.get("citations") or [],
        "signal_count": len(signals) if isinstance(signals, list) else 0,
        "source_count": len(sources) if isinstance(sources, list) else 0,
        "basis_field_count": len(basis) if isinstance(basis, list) else 0,
    }


def _parse_exa_calls(calls: list[EngineCall]) -> dict[str, Any]:
    searches: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for call in calls:
        if call.vendor != "exa" or call.status != "ok":
            continue
        req = call.request_payload or {}
        rsp = call.response_payload or {}
        op = call.operation or ""

        if "query" in req:
            searches.append({
                "query": req.get("query"),
                "search_type": req.get("search_type"),
                "deep_model": req.get("deep_model"),
                "num_results": req.get("num_results"),
                "urls": rsp.get("urls") or [],
                "count": rsp.get("count", 0),
                "latency_ms": call.latency_ms,
            })
        elif "urls" in req or op == "get_contents":
            for item in rsp.get("fetched") or []:
                if not isinstance(item, dict):
                    continue
                url = item.get("url") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                pages.append({
                    "url": url,
                    "title": item.get("title"),
                    "chars": item.get("chars"),
                    "text_preview": item.get("text_preview"),
                    "published_date": item.get("published_date"),
                })

    return {
        "search_count": len(searches),
        "page_count": len(pages),
        "searches": searches,
        "pages": pages,
    }


def _enrich_exa_pages_from_sources(
    exa: dict[str, Any],
    sources: list[Source],
) -> dict[str, Any]:
    """Fill missing text previews from card source snippets (URL match)."""
    by_url: dict[str, str] = {}
    for s in sources:
        if s.url and s.snippet:
            by_url[s.url.strip().lower().rstrip("/")] = s.snippet

    pages = exa.get("pages") or []
    for p in pages:
        if p.get("text_preview"):
            continue
        norm = (p.get("url") or "").strip().lower().rstrip("/")
        if norm in by_url:
            p["text_preview"] = by_url[norm]
            p["snippet_source"] = "card_sources"
    return exa


async def get_company_evidence(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> dict[str, Any] | None:
    company = await session.get(Company, company_id)
    if company is None:
        return None

    card: Card | None = None
    if company.canonical_card_id:
        card = await session.get(Card, company.canonical_card_id)

    if card is None or card.run_id is None:
        return {
            "company_id": str(company_id),
            "run_id": None,
            "card_id": str(card.id) if card else None,
            "collected_at": None,
            "diffbot": None,
            "parallel": None,
            "exa": {"search_count": 0, "page_count": 0, "searches": [], "pages": []},
            "summary": {
                "has_evidence": False,
                "engine_count": 0,
                "total_cost_usd": 0.0,
            },
        }

    run_id = card.run_id
    calls = (
        await session.execute(
            select(EngineCall)
            .where(EngineCall.run_id == run_id)
            .where(EngineCall.vendor.in_(("parallel", "exa", "diffbot")))
            .order_by(EngineCall.created_at.asc())
        )
    ).scalars().all()

    diffbot: dict[str, Any] | None = None
    parallel: dict[str, Any] | None = None
    exa_calls: list[EngineCall] = []

    for call in calls:
        if call.vendor == "diffbot" and diffbot is None and call.status == "ok":
            parsed = _parse_diffbot(call)
            if parsed:
                diffbot = parsed
        elif call.vendor == "parallel" and parallel is None and call.status == "ok":
            parsed = _parse_parallel(call)
            if parsed:
                parallel = parsed
        elif call.vendor == "exa":
            exa_calls.append(call)

    exa = _parse_exa_calls(exa_calls)

    sources: list[Source] = []
    if card:
        sources = (
            await session.execute(
                select(Source).where(Source.card_id == card.id)
            )
        ).scalars().all()
    exa = _enrich_exa_pages_from_sources(exa, sources)

    engine_count = sum(1 for x in (diffbot, parallel) if x) + (1 if exa["page_count"] or exa["search_count"] else 0)
    total_cost = sum(c.cost_usd for c in calls if c.vendor in ("parallel", "exa", "diffbot"))

    return {
        "company_id": str(company_id),
        "run_id": str(run_id),
        "card_id": str(card.id),
        "collected_at": card.created_at.isoformat() if card.created_at else None,
        "diffbot": diffbot,
        "parallel": parallel,
        "exa": exa,
        "summary": {
            "has_evidence": engine_count > 0,
            "engine_count": engine_count,
            "total_cost_usd": round(total_cost, 4),
            "diffbot_score": diffbot.get("score") if diffbot else None,
            "parallel_signals": parallel.get("signal_count") if parallel else 0,
            "exa_pages": exa["page_count"],
            "diffbot_fields": diffbot.get("field_count") if diffbot else 0,
        },
    }
