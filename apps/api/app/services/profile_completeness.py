"""Profile completeness catalog + extraction from ``CompanyCardV1`` JSON.

The 44 must-have parameters are the API contract — any consumer (future UI,
integrations, reports) reads ``card_profile_parameters`` rows materialized at
card persist time instead of recomputing coverage client-side.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

CoverageStatus = Literal["verified", "uncertain", "missing"]
FieldConfidence = Literal["confirmed", "estimated", "inferred", "unknown"]


@dataclass(frozen=True, slots=True)
class ExtractedParam:
    param_key: str
    group_name: str
    sort_order: int
    label: str
    value: Any
    confidence: FieldConfidence
    basis: str | None
    source_refs: list[int]
    coverage_status: CoverageStatus


@dataclass(frozen=True, slots=True)
class ProfileCompletenessSummary:
    completeness_pct: int
    verified_count: int
    uncertain_count: int
    missing_count: int
    total_count: int


@dataclass(frozen=True, slots=True)
class _CatalogEntry:
    param_key: str
    group_name: str
    sort_order: int
    label: str
    pick: Callable[[dict[str, Any]], "_Cell"]


@dataclass(frozen=True, slots=True)
class _Cell:
    value: Any
    confidence: FieldConfidence
    basis: str | None
    source_refs: list[int]
    coverage_status: CoverageStatus


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _status_for(value: Any, confidence: str | None) -> CoverageStatus:
    if _is_empty(value):
        return "missing"
    if confidence == "confirmed":
        return "verified"
    if confidence in ("estimated", "inferred"):
        return "uncertain"
    return "missing"


def _valued(v: Any) -> _Cell:
    value = v.get("value") if isinstance(v, dict) else None
    confidence = (v.get("confidence") if isinstance(v, dict) else None) or "unknown"
    basis = v.get("basis") if isinstance(v, dict) else None
    sources = v.get("sources") if isinstance(v, dict) else None
    source_refs = [int(x) for x in sources] if isinstance(sources, list) else []
    conf: FieldConfidence = confidence if confidence in ("confirmed", "estimated", "inferred", "unknown") else "unknown"
    return _Cell(
        value=value,
        confidence=conf,
        basis=basis if isinstance(basis, str) else None,
        source_refs=source_refs,
        coverage_status=_status_for(value, conf),
    )


def _plain(value: Any) -> _Cell:
    empty = _is_empty(value)
    return _Cell(
        value=value,
        confidence="unknown" if empty else "confirmed",
        basis=None,
        source_refs=[],
        coverage_status="missing" if empty else "verified",
    )


def _pick_social_stats(card: dict[str, Any]) -> _Cell:
    b = card.get("brand_marketing_sentiment") or {}
    cands = [
        b.get("instagram_followers"),
        b.get("tiktok_followers"),
        b.get("linkedin_followers"),
    ]
    cands = [x for x in cands if isinstance(x, dict) and not _is_empty(x.get("value"))]
    if not cands:
        return _Cell(None, "unknown", None, [], "missing")

    def _rank(x: dict[str, Any]) -> int:
        c = x.get("confidence")
        if c == "confirmed":
            return 3
        if c == "estimated":
            return 2
        if c == "inferred":
            return 1
        return 0

    best = max(cands, key=_rank)
    parts: list[str] = []
    for key, prefix in (
        ("instagram_followers", "IG"),
        ("tiktok_followers", "TT"),
        ("linkedin_followers", "LI"),
    ):
        node = b.get(key) or {}
        val = node.get("value") if isinstance(node, dict) else None
        if not _is_empty(val):
            parts.append(f"{prefix} {val:,}" if isinstance(val, (int, float)) else f"{prefix} {val}")
    value = " · ".join(parts)
    conf = best.get("confidence") or "unknown"
    field_conf: FieldConfidence = conf if conf in ("confirmed", "estimated", "inferred", "unknown") else "unknown"
    refs = best.get("sources") if isinstance(best.get("sources"), list) else []
    source_refs = [int(x) for x in refs]
    return _Cell(
        value=value,
        confidence=field_conf,
        basis=best.get("basis") if isinstance(best.get("basis"), str) else None,
        source_refs=source_refs,
        coverage_status=_status_for(value, field_conf),
    )


def _pick_distribution_channels(card: dict[str, Any]) -> _Cell:
    d = card.get("distribution_and_channels") or {}
    present: list[str] = []
    for key, label in (
        ("dtc_presence", "DTC"),
        ("retail_presence", "Retail"),
        ("wholesale_presence", "Wholesale"),
        ("marketplace_presence", "Marketplace"),
    ):
        val = d.get(key)
        if val and val != "none":
            present.append(f"{label} ({val})")
    return _plain(present or None)


def _pick_product_claims(card: dict[str, Any]) -> _Cell:
    claims: list[str] = []
    prods = (card.get("products_and_skus") or {}).get("products") or []
    if isinstance(prods, list):
        for p in prods:
            if isinstance(p, dict):
                for c in p.get("claims") or []:
                    if isinstance(c, str):
                        claims.append(c)
    return _plain(claims or None)


def _pick_lawsuits_recalls(card: dict[str, Any]) -> _Cell:
    r = card.get("legal_regulatory_risk") or {}
    arr: list[str] = []
    for key in ("lawsuits", "product_recalls"):
        items = r.get(key)
        if isinstance(items, list):
            arr.extend(str(x) for x in items)
    return _plain(arr or None)


def _pick_overall_confidence(card: dict[str, Any]) -> _Cell:
    sac = card.get("sources_and_confidence") or {}
    oc = sac.get("overall_confidence")
    if not oc or oc == "unknown":
        return _Cell(None, "unknown", None, [], "missing")
    status: CoverageStatus = "verified" if oc == "high" else "uncertain"
    conf: FieldConfidence = "confirmed" if oc == "high" else "estimated"
    basis = sac.get("coverage_summary")
    return _Cell(
        value=oc,
        confidence=conf,
        basis=basis if isinstance(basis, str) else None,
        source_refs=[],
        coverage_status=status,
    )


def _pick_source_urls(card: dict[str, Any]) -> _Cell:
    srcs = (card.get("sources_and_confidence") or {}).get("sources")
    n = len(srcs) if isinstance(srcs, list) else 0
    return _plain(f"{n} sources" if n else None)


def _pick_last_funding_round(card: dict[str, Any]) -> _Cell:
    fi = card.get("funding_and_investors") or {}
    rt = fi.get("last_round_type")
    if not rt:
        return _plain(None)
    rd = fi.get("last_round_date")
    value = f"{rt} · {rd}" if rd else str(rt)
    return _plain(value)


def _pick_patents_trademarks(card: dict[str, Any]) -> _Cell:
    t = card.get("technology_ip_defensibility") or {}
    patents = t.get("patents_granted") or t.get("patents")
    trademarks = t.get("trademarks")
    combined: list[Any] = []
    if isinstance(patents, list):
        combined.extend(patents)
    if isinstance(trademarks, list):
        combined.extend(trademarks)
    return _plain(combined or None)


def _catalog() -> list[_CatalogEntry]:
  """Stable 44-parameter catalog (sort_order is global display order)."""
  entries: list[tuple[str, str, str, Callable[[dict[str, Any]], _Cell]]] = [
      # Identity
      ("company_name", "Identity", "Company name", lambda c: _plain((c.get("company_identity") or {}).get("company_name"))),
      ("website", "Identity", "Website", lambda c: _plain((c.get("company_identity") or {}).get("website") or (c.get("company_identity") or {}).get("domain"))),
      ("legal_entity", "Identity", "Legal entity", lambda c: _plain((c.get("company_identity") or {}).get("legal_entity_name"))),
      ("founded_date", "Identity", "Founded date", lambda c: _plain((c.get("company_identity") or {}).get("founded_date") or (c.get("company_identity") or {}).get("founded_year"))),
      ("headquarters", "Identity", "Headquarters", lambda c: _plain((c.get("company_identity") or {}).get("headquarters"))),
      ("company_status", "Identity", "Status", lambda c: _plain(
          (c.get("company_identity") or {}).get("status")
          if (c.get("company_identity") or {}).get("status") not in (None, "unknown")
          else None
      )),
      # Classification
      ("industry", "Classification", "Industry", lambda c: _plain((c.get("classification") or {}).get("industry"))),
      ("sector", "Classification", "Sector", lambda c: _plain((c.get("classification") or {}).get("sector"))),
      ("category", "Classification", "Category", lambda c: _plain((c.get("classification") or {}).get("category"))),
      ("subcategory", "Classification", "Subcategory", lambda c: _plain((c.get("classification") or {}).get("subcategory"))),
      # People
      ("ceo", "People", "CEO", lambda c: _plain(((c.get("people_and_decision_map") or {}).get("ceo") or {}).get("name"))),
      ("founders", "People", "Founders", lambda c: _plain((c.get("people_and_decision_map") or {}).get("founders"))),
      ("key_executives", "People", "Key executives", lambda c: _plain((c.get("people_and_decision_map") or {}).get("executives"))),
      ("decision_map", "People", "Decision map", lambda c: _plain((c.get("people_and_decision_map") or {}).get("decision_map"))),
      # Traction
      ("employee_count", "Traction", "Employee count", lambda c: _valued((c.get("traction_and_momentum") or {}).get("employee_count_estimate"))),
      ("employee_growth", "Traction", "Employee growth", lambda c: _valued((c.get("traction_and_momentum") or {}).get("employee_growth_90d"))),
      # Products
      ("products", "Products", "Products", lambda c: _plain((c.get("products_and_skus") or {}).get("products"))),
      ("sku_count", "Products", "SKUs (count)", lambda c: _valued((c.get("products_and_skus") or {}).get("sku_count"))),
      ("product_claims", "Products", "Product claims", _pick_product_claims),
      ("pricing", "Products", "Pricing", lambda c: _plain((c.get("products_and_skus") or {}).get("pricing_summary"))),
      # Distribution
      ("store_count", "Distribution", "Store count", lambda c: _valued((c.get("distribution_and_channels") or {}).get("store_count_estimate"))),
      ("retail_partners", "Distribution", "Retail partners", lambda c: _plain((c.get("distribution_and_channels") or {}).get("retail_partners"))),
      ("distribution_channels", "Distribution", "Distribution channels", _pick_distribution_channels),
      # Business Model
      ("business_model_summary", "Business Model", "Business model", lambda c: _valued((c.get("business_model") or {}).get("business_model_summary"))),
      # Financials
      ("revenue_estimate", "Financials", "Revenue estimate", lambda c: _valued((c.get("financials") or {}).get("revenue_estimate"))),
      # Funding
      ("total_funding", "Funding", "Funding raised (total)", lambda c: _valued((c.get("funding_and_investors") or {}).get("total_funding"))),
      ("last_funding_round", "Funding", "Last funding round", _pick_last_funding_round),
      ("investors", "Funding", "Investors", lambda c: _plain((c.get("funding_and_investors") or {}).get("known_investors"))),
      ("valuation_estimate", "Funding", "Valuation estimate", lambda c: _valued((c.get("funding_and_investors") or {}).get("last_valuation_estimate"))),
      # Market
      ("similar_companies", "Market", "Similar companies", lambda c: _plain((c.get("market_and_competitors") or {}).get("private_comparables"))),
      ("competitors", "Market", "Competitors", lambda c: _plain((c.get("market_and_competitors") or {}).get("direct_competitors"))),
      ("market_category_trend", "Market", "Market/category trend", lambda c: _plain((c.get("market_and_competitors") or {}).get("consumer_trends"))),
      # Brand & Sentiment
      ("social_stats", "Brand & Sentiment", "Social stats", _pick_social_stats),
      ("social_growth", "Brand & Sentiment", "Social growth", lambda c: _valued((c.get("traction_and_momentum") or {}).get("social_follower_growth_90d"))),
      ("consumer_sentiment", "Brand & Sentiment", "Consumer sentiment", lambda c: _valued((c.get("products_and_skus") or {}).get("review_summary"))),
      ("news_mentions", "Brand & Sentiment", "News mentions", lambda c: _plain((c.get("traction_and_momentum") or {}).get("awards"))),
      ("partnerships", "Brand & Sentiment", "Partnerships", lambda c: _plain((c.get("traction_and_momentum") or {}).get("new_distributor_partnerships"))),
      # Tech & IP
      ("patents_trademarks", "Tech & IP", "Patents / trademarks", _pick_patents_trademarks),
      # Risk
      ("regulatory_risks", "Risk", "Regulatory risks", lambda c: _plain(
          (c.get("legal_regulatory_risk") or {}).get("overall_risk_level")
          if (c.get("legal_regulatory_risk") or {}).get("overall_risk_level") not in (None, "unknown")
          else None
      )),
      ("lawsuits_recalls", "Risk", "Lawsuits / recalls", _pick_lawsuits_recalls),
      # Strategic Fit
      ("strategic_fit", "Strategic Fit", "Strategic fit", lambda c: _valued((c.get("strategic_fit") or {}).get("fit_summary"))),
      ("recommended_next_action", "Strategic Fit", "Recommended next action", lambda c: _valued((c.get("strategic_fit") or {}).get("recommended_next_action"))),
      # Provenance
      ("source_urls", "Provenance", "Source URLs", _pick_source_urls),
      ("overall_confidence", "Provenance", "Overall confidence", _pick_overall_confidence),
  ]
  return [
      _CatalogEntry(
          param_key=key,
          group_name=group,
          sort_order=i,
          label=label,
          pick=pick,
      )
      for i, (key, group, label, pick) in enumerate(entries)
  ]


CATALOG: list[_CatalogEntry] = _catalog()
CATALOG_PARAM_COUNT = len(CATALOG)


def extract_profile_parameters(card: dict[str, Any]) -> list[ExtractedParam]:
    """Flatten a ``CompanyCardV1`` dict into 44 must-have parameter rows."""
    out: list[ExtractedParam] = []
    for entry in CATALOG:
        cell = entry.pick(card)
        out.append(
            ExtractedParam(
                param_key=entry.param_key,
                group_name=entry.group_name,
                sort_order=entry.sort_order,
                label=entry.label,
                value=cell.value,
                confidence=cell.confidence,
                basis=cell.basis,
                source_refs=cell.source_refs,
                coverage_status=cell.coverage_status,
            )
        )
    return out


def summarize_profile_completeness(params: list[ExtractedParam]) -> ProfileCompletenessSummary:
    verified = sum(1 for p in params if p.coverage_status == "verified")
    uncertain = sum(1 for p in params if p.coverage_status == "uncertain")
    missing = sum(1 for p in params if p.coverage_status == "missing")
    total = len(params)
    pct = round(((verified + uncertain * 0.5) / max(total, 1)) * 100)
    return ProfileCompletenessSummary(
        completeness_pct=pct,
        verified_count=verified,
        uncertain_count=uncertain,
        missing_count=missing,
        total_count=total,
    )
