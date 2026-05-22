"""The 16 Company Card blocks.

Field selection follows the locked schema spec at
`attached_assets/Pasted-1-Company-Identity-Parameter-...txt`. Tiers attached
to each field reflect what Parallel + Exa can reliably extract today; Tier C
fields are stubbed by the worker (see `app.schemas.tiers`).

Convention:
- Plain types for hard facts (company name, URLs, list of competitors).
- `Valued[T]` for anything estimated, inferred, or synthesized.
- Industry-specific extensions live in optional nested sub-blocks (e.g.
  `products_and_skus.cpg_specific`) so non-CPG cards don't carry junk fields.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import (
    BusinessType,
    CompanyStatus,
    MoneyRange,
    Period,
    Source,
    Valued,
    tier_a,
    tier_b,
    tier_c,
)

# ── Block 1: Company Identity ───────────────────────────────────────────────


class SocialHandles(BaseModel):
    model_config = ConfigDict(extra="ignore")
    linkedin: str | None = None
    twitter: str | None = None
    instagram: str | None = None
    tiktok: str | None = None
    youtube: str | None = None
    facebook: str | None = None
    other: list[str] = Field(default_factory=list)


class CompanyIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_name: str | None = None
    legal_entity_name: str | None = None
    website: str | None = None
    domain: str | None = None
    logo_url: str | None = None
    tagline: str | None = None
    description: str | None = None
    founded_year: int | None = None
    founded_date: str | None = None  # YYYY-MM-DD when known precisely
    headquarters: str | None = None
    operating_countries: list[str] = Field(default_factory=list)
    status: CompanyStatus = "unknown"
    parent_company: str | None = None
    former_names: list[str] = Field(default_factory=list)
    associated_brands: list[str] = Field(default_factory=list)
    business_registration: str | None = None  # e.g. Delaware C-Corp #1234567
    company_linkedin: str | None = None
    social_handles: SocialHandles = Field(default_factory=SocialHandles)


# ── Block 2: Classification ─────────────────────────────────────────────────


class Classification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    industry: str | None = None
    sector: str | None = None
    category: str | None = None
    subcategory: str | None = None
    product_vertical: str | None = None
    business_type: BusinessType = "unknown"
    regulated_category: Valued[bool] = tier_a(
        "Is this product in a regulated category (FDA/Health Canada/TGA/etc.)?"
    )
    consumer_packaged_goods: Valued[bool] = tier_a("Is this a CPG product?")
    healthcare_claim_exposure: Valued[bool] = tier_a(
        "Does the product make medical/healthcare claims?"
    )


# ── Block 3: Products & SKU Intelligence ────────────────────────────────────


class Product(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    category: str | None = None
    hero: bool = False
    formats: list[str] = Field(default_factory=list)
    flavours_or_variants: list[str] = Field(default_factory=list)
    pack_sizes: list[str] = Field(default_factory=list)
    price_points_usd: list[float] = Field(default_factory=list)
    subscription_option: bool | None = None
    launch_date: str | None = None  # YYYY-MM-DD
    discontinued: bool = False
    claims: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    amazon_url: str | None = None
    dtc_url: str | None = None
    sources: list[int] = Field(default_factory=list)


class CPGSpecific(BaseModel):
    """Sub-block populated only for CPG / supplement / functional bev / nicotine.

    Stays `None` at the parent level for non-CPG companies.
    """

    model_config = ConfigDict(extra="ignore")
    ingredients: list[str] = Field(default_factory=list)
    active_ingredients: list[str] = Field(default_factory=list)
    health_or_function_claims: list[str] = Field(default_factory=list)
    claim_types: list[
        Literal[
            "energy",
            "sleep",
            "stress",
            "cognitive",
            "metabolic",
            "nicotine_alternative",
            "harm_reduction",
            "immunity",
            "beauty",
            "performance",
            "other",
        ]
    ] = Field(default_factory=list)
    proprietary_blend: bool | None = None
    dosage_disclosed: bool | None = None
    third_party_tested: bool | None = None


class ProductsAndSkus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    product_categories: list[str] = Field(default_factory=list)
    products: list[Product] = Field(default_factory=list)
    sku_count: Valued[int] = tier_b("Approximate SKU count across the catalog.")
    hero_product: str | None = None
    pricing_summary: str | None = None
    product_roadmap_clues: list[str] = Field(default_factory=list)
    discontinued_products: list[str] = Field(default_factory=list)
    similar_competing_products: list[str] = Field(default_factory=list)
    retailer_listings: list[str] = Field(default_factory=list)  # "Walmart", "Target", "Amazon"
    review_summary: Valued[str] = tier_a(
        "Aggregate consumer review sentiment (1-paragraph summary)."
    )
    complaint_themes: list[str] = Field(default_factory=list)
    cpg_specific: CPGSpecific | None = None


# ── Block 4: Team, People & Decision Map ────────────────────────────────────


class Person(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    title: str | None = None
    linkedin_url: str | None = None
    is_founder: bool = False
    is_board_member: bool = False
    is_advisor: bool = False
    prior_companies: list[str] = Field(default_factory=list)
    prior_exits: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    domain_expertise: list[str] = Field(default_factory=list)
    joined: str | None = None  # YYYY-MM-DD
    departed: str | None = None  # YYYY-MM-DD if past exec
    sources: list[int] = Field(default_factory=list)


DecisionRole = Literal[
    "economic_buyer",  # CEO / founder — can approve investment/partnership/M&A
    "strategic_sponsor",  # cares about partnership / corporate value
    "technical_evaluator",  # product feasibility
    "commercial_lead",  # retail, distribution, revenue
    "regulatory_lead",  # health/nicotine/supplements compliance
    "investor_influence",  # lead investor / board member with sway
    "gatekeeper",  # EA, chief of staff
    "founder",
]


class DecisionMapEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    person_name: str
    role_in_decision: DecisionRole
    rationale: str | None = None
    outreach_recommendation: str | None = None  # "Best contact for partnership"


class PeopleAndDecisionMap(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ceo: Person | None = None
    founders: list[Person] = Field(default_factory=list)
    executives: list[Person] = Field(default_factory=list)
    board: list[Person] = Field(default_factory=list)
    advisors: list[Person] = Field(default_factory=list)
    recent_hires: list[Person] = Field(default_factory=list)
    recent_departures: list[Person] = Field(default_factory=list)
    decision_map: list[DecisionMapEntry] = Field(default_factory=list)
    best_contact_for_partnership: str | None = None
    best_contact_for_investment: str | None = None
    best_contact_for_acquisition: str | None = None


# ── Block 5: Financials ─────────────────────────────────────────────────────


class Financials(BaseModel):
    model_config = ConfigDict(extra="ignore")
    revenue_estimate: Valued[MoneyRange] = tier_b(
        "Estimated annual revenue (range, with basis)."
    )
    revenue_by_geography: Valued[dict[str, float]] = tier_b(
        "Revenue split by geography (country/region → share 0-1)."
    )
    revenue_growth_yoy: Valued[float] = tier_b("Estimated YoY revenue growth (0-N).")
    gross_margin_estimate: Valued[float] = tier_b("Estimated gross margin (0-1).")
    profitability_status: Valued[
        Literal["profitable", "break_even", "unprofitable", "unknown"]
    ] = tier_b("Best-guess profitability stance.")
    funding_raised_total: Valued[MoneyRange] = tier_a("Sum of disclosed funding rounds.")
    last_valuation_estimate: Valued[MoneyRange] = tier_b("Most recent valuation, if known.")
    debt_financing: Valued[MoneyRange] = tier_b("Disclosed debt financing.")
    grants: Valued[MoneyRange] = tier_b("Public grants received.")
    crowdfunding_total: Valued[MoneyRange] = tier_a("Total crowdfunding raised.")
    aov_estimate: Valued[float] = tier_c(
        "Average order value (USD).", gap_reason="requires_traffic_or_pos_data"
    )
    cac_estimate: Valued[float] = tier_c(
        "Customer acquisition cost.", gap_reason="requires_marketing_data"
    )
    ltv_estimate: Valued[float] = tier_c(
        "Lifetime value.", gap_reason="requires_marketing_data"
    )
    revenue_by_channel: Valued[dict[str, float]] = tier_c(
        "Revenue split by channel.", gap_reason="requires_pos_or_company_disclosure"
    )
    customer_concentration: Valued[str] = tier_b(
        "Description of customer concentration risk."
    )
    channel_concentration: Valued[str] = tier_b("Description of channel concentration.")


# ── Block 6: Funding & Investors ────────────────────────────────────────────


RoundType = Literal[
    "pre_seed",
    "seed",
    "series_a",
    "series_b",
    "series_c",
    "series_d_plus",
    "convertible",
    "safe",
    "debt",
    "grant",
    "crowdfunding",
    "ipo",
    "secondary",
    "other",
]


class FundingRound(BaseModel):
    model_config = ConfigDict(extra="ignore")
    round_type: RoundType
    date: str | None = None  # YYYY-MM-DD
    amount: MoneyRange | None = None
    lead_investors: list[str] = Field(default_factory=list)
    other_investors: list[str] = Field(default_factory=list)
    strategic_investors: list[str] = Field(default_factory=list)
    valuation: MoneyRange | None = None
    sources: list[int] = Field(default_factory=list)


class FundingAndInvestors(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_funding: Valued[MoneyRange] = tier_a("Total disclosed across all rounds.")
    rounds: list[FundingRound] = Field(default_factory=list)
    last_round_type: RoundType | None = None
    last_round_date: str | None = None
    time_since_last_raise_months: Valued[int] = tier_a(
        "Months since last disclosed round."
    )
    current_fundraising_status: Valued[
        Literal["raising", "recently_raised", "between_rounds", "unknown"]
    ] = tier_b("Is the company actively raising?")
    likely_next_round: Valued[RoundType] = tier_b("Inferred next round type.")
    known_investors: list[str] = Field(default_factory=list)
    lead_investors: list[str] = Field(default_factory=list)
    strategic_investors: list[str] = Field(default_factory=list)
    angel_investors: list[str] = Field(default_factory=list)
    board_representation: list[str] = Field(default_factory=list)
    investor_quality_summary: Valued[str] = tier_a(
        "Synthesized read on investor quality / category fit."
    )
    accelerator_history: list[str] = Field(default_factory=list)
    follow_on_probability: Valued[
        Literal["high", "medium", "low", "unknown"]
    ] = tier_b("Will existing investors likely follow on?")
    acquisition_pressure: Valued[
        Literal["high", "medium", "low", "unknown"]
    ] = tier_b("Pressure indicators toward acquisition.")


# ── Block 7: Traction & Momentum ────────────────────────────────────────────


class TractionAndMomentum(BaseModel):
    model_config = ConfigDict(extra="ignore")
    employee_count_estimate: Valued[int] = tier_b("LinkedIn-derived employee count.")
    employee_growth_90d: Valued[float] = tier_b("LinkedIn growth % over 90d.")
    hiring_pace: Valued[
        Literal["accelerating", "steady", "slowing", "frozen", "unknown"]
    ] = tier_a("Hiring trend (from job posts + headcount).")
    notable_recent_hires: list[str] = Field(default_factory=list)
    notable_recent_departures: list[str] = Field(default_factory=list)
    retail_expansion_recent: list[str] = Field(default_factory=list)
    new_distributor_partnerships: list[str] = Field(default_factory=list)
    new_market_launches: list[str] = Field(default_factory=list)
    new_product_launches: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    conference_appearances: list[str] = Field(default_factory=list)
    podcast_interviews: list[str] = Field(default_factory=list)
    web_traffic_monthly: Valued[int] = tier_c(
        "Estimated monthly web visits.", gap_reason="requires_similarweb"
    )
    web_traffic_growth_90d: Valued[float] = tier_c(
        "90-day traffic growth.", gap_reason="requires_similarweb"
    )
    social_follower_growth_90d: Valued[float] = tier_c(
        "Aggregate social follower growth.", gap_reason="requires_phyllo_or_modash"
    )
    social_engagement_rate: Valued[float] = tier_c(
        "Cross-platform engagement rate.", gap_reason="requires_phyllo_or_modash"
    )
    search_volume_growth_90d: Valued[float] = tier_c(
        "Branded search volume growth.", gap_reason="requires_dataforseo"
    )
    out_of_stock_signals: list[str] = Field(default_factory=list)


# ── Block 8: Distribution & Channels ────────────────────────────────────────


ChannelPresence = Literal["none", "limited", "regional", "national", "international"]


class DistributionAndChannels(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dtc_presence: ChannelPresence = "none"
    retail_presence: ChannelPresence = "none"
    wholesale_presence: ChannelPresence = "none"
    marketplace_presence: ChannelPresence = "none"
    amazon_listings: list[str] = Field(default_factory=list)
    on_instacart: bool | None = None
    on_uber_eats: bool | None = None
    on_doordash: bool | None = None
    on_tiktok_shop: bool | None = None
    store_count_estimate: Valued[int] = tier_b("Total brick-and-mortar door count.")
    retail_partners: list[str] = Field(default_factory=list)
    distributor_partners: list[str] = Field(default_factory=list)
    broker_relationships: list[str] = Field(default_factory=list)
    geographic_coverage: list[str] = Field(default_factory=list)
    online_vs_offline_split: Valued[str] = tier_b("Approx. online vs offline %.")
    retail_expansion_timeline: list[str] = Field(default_factory=list)
    club_store_presence: bool | None = None
    convenience_store_presence: bool | None = None
    pharmacy_presence: bool | None = None
    grocery_presence: bool | None = None
    specialty_retail_presence: bool | None = None
    international_distributors: list[str] = Field(default_factory=list)
    retail_velocity_proxy: Valued[str] = tier_c(
        "Sell-through velocity proxy.", gap_reason="requires_spins_or_iri"
    )


# ── Block 9: Market & Competitive Landscape ─────────────────────────────────


class MarketAndCompetitors(BaseModel):
    model_config = ConfigDict(extra="ignore")
    direct_competitors: list[str] = Field(default_factory=list)
    indirect_competitors: list[str] = Field(default_factory=list)
    substitute_products: list[str] = Field(default_factory=list)
    public_comparables: list[str] = Field(default_factory=list)
    private_comparables: list[str] = Field(default_factory=list)
    recently_funded_comparables: list[str] = Field(default_factory=list)
    recently_acquired_comparables: list[str] = Field(default_factory=list)
    category_leaders: list[str] = Field(default_factory=list)
    emerging_challengers: list[str] = Field(default_factory=list)
    market_size: Valued[MoneyRange] = tier_b("Addressable market size.")
    market_growth_rate: Valued[float] = tier_b("Annual market growth rate.")
    category_growth_drivers: list[str] = Field(default_factory=list)
    consumer_trends: list[str] = Field(default_factory=list)
    regulatory_trends: list[str] = Field(default_factory=list)
    competitive_advantage: Valued[str] = tier_a("Synthesized competitive moat.")
    weaknesses: Valued[str] = tier_a("Honest weaknesses vs competitors.")
    threat_level_to_incumbents: Valued[
        Literal["low", "medium", "high", "unknown"]
    ] = tier_a("Threat level to category incumbents.")
    white_space_opportunity: Valued[str] = tier_a("White-space narrative.")


# ── Block 10: Business Model ────────────────────────────────────────────────


class BusinessModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    business_model_summary: Valued[str] = tier_a("One-paragraph business model.")
    revenue_streams: list[
        Literal[
            "dtc",
            "retail",
            "subscription",
            "wholesale",
            "licensing",
            "marketplace",
            "enterprise",
            "insurance_reimbursement",
            "franchise",
            "razor_razorblade",
            "advertising",
            "other",
        ]
    ] = Field(default_factory=list)
    recurring_revenue: Valued[bool] = tier_a("Does the model produce recurring revenue?")
    repeat_purchase_potential: Valued[
        Literal["high", "medium", "low", "unknown"]
    ] = tier_a("Likelihood of repeat purchase.")
    margin_profile: Valued[
        Literal["high", "medium", "low", "unknown"]
    ] = tier_b("Estimated margin profile.")
    scalability: Valued[
        Literal["high", "medium", "low", "unknown"]
    ] = tier_a("How scalable is the model?")
    operational_complexity: Valued[
        Literal["high", "medium", "low", "unknown"]
    ] = tier_a("Ops complexity.")
    supply_chain_complexity: Valued[
        Literal["high", "medium", "low", "unknown"]
    ] = tier_a("Supply chain complexity.")
    inventory_risk: Valued[
        Literal["high", "medium", "low", "unknown"]
    ] = tier_a("Inventory risk.")
    regulatory_dependency: Valued[
        Literal["high", "medium", "low", "unknown"]
    ] = tier_a("How regulatory-bound is the business?")
    platform_dependency: list[str] = Field(default_factory=list)  # ["Amazon", "TikTok"]


# ── Block 11: Strategic Fit (NORAD-specific synthesis) ──────────────────────


class StrategicFit(BaseModel):
    """Synthesized by Claude for NORAD's BD use case."""

    model_config = ConfigDict(extra="ignore")
    fit_summary: Valued[str] = tier_a("Why does this company matter to Growth Maschine?")
    portfolio_adjacency: Valued[str] = tier_a("Adjacency to existing portfolio / interests.")
    consumer_trend_alignment: Valued[str] = tier_a("Trend alignment.")
    category_growth_alignment: Valued[str] = tier_a("Category-growth thesis fit.")
    geographic_fit: Valued[str] = tier_a("Geographic relevance.")
    distribution_overlap: Valued[str] = tier_a("Distribution overlap with our network.")
    why_now: Valued[str] = tier_a("Why now is the right moment.")
    recommended_next_action: Valued[
        Literal[
            "outreach_partnership",
            "outreach_investment",
            "outreach_acquisition",
            "monitor",
            "pass",
            "unknown",
        ]
    ] = tier_a("Recommended action.")
    recommended_action_rationale: Valued[str] = tier_a("Rationale for the recommendation.")


# ── Block 12: Legal, Regulatory & Compliance Risk ───────────────────────────


RiskLevel = Literal["none", "low", "medium", "high", "critical", "unknown"]


class RegulatedSpecific(BaseModel):
    """For nicotine / cannabis / supplements / healthcare only."""

    model_config = ConfigDict(extra="ignore")
    nicotine_regulation_exposure: RiskLevel = "unknown"
    tobacco_regulation_exposure: RiskLevel = "unknown"
    cannabis_regulation_exposure: RiskLevel = "unknown"
    supplement_claim_risk: RiskLevel = "unknown"
    healthcare_claim_risk: RiskLevel = "unknown"
    age_gated_product_exposure: bool = False
    youth_marketing_risk: RiskLevel = "unknown"
    license_status: Valued[str] = tier_a("Operating license status.")
    required_approvals: list[str] = Field(default_factory=list)


class LegalRegulatoryRisk(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lawsuits: list[str] = Field(default_factory=list)
    regulatory_warnings: list[str] = Field(default_factory=list)  # FDA warning letters, etc.
    product_recalls: list[str] = Field(default_factory=list)
    fda_issues: list[str] = Field(default_factory=list)
    ftc_issues: list[str] = Field(default_factory=list)
    advertising_claims_risk: RiskLevel = "unknown"
    labelling_compliance: Valued[str] = tier_a("Labelling compliance posture.")
    packaging_compliance: Valued[str] = tier_a("Packaging compliance posture.")
    environmental_claims_risk: RiskLevel = "unknown"
    data_privacy_risk: RiskLevel = "unknown"
    ip_litigation: list[str] = Field(default_factory=list)
    employment_disputes: list[str] = Field(default_factory=list)
    founder_controversies: list[str] = Field(default_factory=list)
    negative_press: list[str] = Field(default_factory=list)
    consumer_complaints_themes: list[str] = Field(default_factory=list)
    safety_incidents: list[str] = Field(default_factory=list)
    sanctions_watchlist: bool = False
    overall_risk_level: RiskLevel = "unknown"
    regulated_specific: RegulatedSpecific | None = None


# ── Block 13: Brand, Marketing & Consumer Sentiment ─────────────────────────


SentimentBand = Literal["very_positive", "positive", "neutral", "negative", "very_negative", "unknown"]


class BrandMarketingSentiment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    brand_positioning: Valued[str] = tier_a("Brand positioning in one paragraph.")
    brand_message: Valued[str] = tier_a("Brand message / promise.")
    target_audience: Valued[str] = tier_a("Target audience description.")
    customer_persona: Valued[str] = tier_a("Primary customer persona.")
    instagram_followers: Valued[int] = tier_a("Instagram follower count.")
    tiktok_followers: Valued[int] = tier_a("TikTok follower count.")
    linkedin_followers: Valued[int] = tier_a("LinkedIn follower count.")
    twitter_followers: Valued[int] = tier_a("X/Twitter follower count.")
    youtube_subscribers: Valued[int] = tier_a("YouTube subscribers.")
    engagement_rate: Valued[float] = tier_c(
        "Average engagement rate.", gap_reason="requires_phyllo_or_modash"
    )
    influencer_activity_summary: Valued[str] = tier_a("Influencer footprint summary.")
    ugc_volume: Valued[
        Literal["high", "medium", "low", "none", "unknown"]
    ] = tier_a("User-generated content volume.")
    tiktok_virality_signal: Valued[str] = tier_a("Notable viral moments.")
    founder_brand_strength: Valued[
        Literal["high", "medium", "low", "none", "unknown"]
    ] = tier_a("How visible is the founder publicly?")
    paid_ads_activity: Valued[str] = tier_a("Paid-ads presence (qualitative).")
    seo_presence_summary: Valued[str] = tier_a("SEO posture.")
    branded_search_volume: Valued[int] = tier_c(
        "Branded search volume.", gap_reason="requires_dataforseo"
    )
    review_sentiment: SentimentBand = "unknown"
    reddit_sentiment: SentimentBand = "unknown"
    media_sentiment: SentimentBand = "unknown"
    brand_controversies: list[str] = Field(default_factory=list)
    premium_vs_mass: Valued[
        Literal["premium", "mid", "mass", "luxury", "unknown"]
    ] = tier_a("Positioning band.")
    community_strength: Valued[
        Literal["strong", "moderate", "weak", "none", "unknown"]
    ] = tier_a("Community / fan base strength.")


# ── Block 14: Technology, IP & Defensibility ────────────────────────────────


class TechnologyIpDefensibility(BaseModel):
    model_config = ConfigDict(extra="ignore")
    patents_granted: list[str] = Field(default_factory=list)
    patent_applications: list[str] = Field(default_factory=list)
    trademarks: list[str] = Field(default_factory=list)
    proprietary_formulas: list[str] = Field(default_factory=list)
    proprietary_manufacturing_process: Valued[str] = tier_a(
        "Notable manufacturing IP."
    )
    scientific_backing: Valued[str] = tier_a("Strength of scientific backing.")
    clinical_studies: list[str] = Field(default_factory=list)
    scientific_advisory_board: list[str] = Field(default_factory=list)
    published_studies: list[str] = Field(default_factory=list)
    rd_team_signal: Valued[str] = tier_a("R&D team strength signal.")
    data_assets: Valued[str] = tier_a("Notable proprietary data assets.")
    technology_stack: list[str] = Field(default_factory=list)
    app_or_platform_layer: Valued[str] = tier_a("Any platform/app component.")
    manufacturing_moat: Valued[
        Literal["high", "medium", "low", "none", "unknown"]
    ] = tier_a("Manufacturing moat.")
    distribution_moat: Valued[
        Literal["high", "medium", "low", "none", "unknown"]
    ] = tier_a("Distribution moat.")
    brand_moat: Valued[
        Literal["high", "medium", "low", "none", "unknown"]
    ] = tier_a("Brand moat.")
    regulatory_moat: Valued[
        Literal["high", "medium", "low", "none", "unknown"]
    ] = tier_a("Regulatory moat (license / approval barriers).")
    supply_chain_moat: Valued[
        Literal["high", "medium", "low", "none", "unknown"]
    ] = tier_a("Supply-chain moat.")
    network_effects: Valued[
        Literal["high", "medium", "low", "none", "unknown"]
    ] = tier_a("Any network effects.")
    exclusive_partnerships: list[str] = Field(default_factory=list)
    exclusive_licenses: list[str] = Field(default_factory=list)


# ── Block 15: Signals ────────────────────────────────────────────────────────


SignalType = Literal["growth", "fundraising", "acquisition", "partnership", "risk", "strategic"]


class Signal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: SignalType
    subtype: str | None = None  # e.g. "store_expansion", "exec_hire"
    date: str | None = None  # YYYY-MM-DD
    headline: str
    evidence: str | None = None
    weight: int = Field(default=5, ge=1, le=10)
    sources: list[int] = Field(default_factory=list)


# ── Block 16: Scores ────────────────────────────────────────────────────────


class Scores(BaseModel):
    """0–100 across the dimensions surfaced in the UI. Computed by Claude."""

    model_config = ConfigDict(extra="ignore")
    growth: int | None = Field(default=None, ge=0, le=100)
    momentum: int | None = Field(default=None, ge=0, le=100)
    fundraising_likelihood: int | None = Field(default=None, ge=0, le=100)
    acquisition_likelihood: int | None = Field(default=None, ge=0, le=100)
    partnership_fit: int | None = Field(default=None, ge=0, le=100)
    strategic_fit: int | None = Field(default=None, ge=0, le=100)
    risk: int | None = Field(default=None, ge=0, le=100)
    overall: int | None = Field(default=None, ge=0, le=100)
    rationale: str | None = None


# ── Sources & confidence registry ───────────────────────────────────────────


class SourcesAndConfidence(BaseModel):
    """Top-level registry of source URLs. Fields reference by `id` index."""

    model_config = ConfigDict(extra="ignore")
    sources: list[Source] = Field(default_factory=list)
    coverage_summary: str | None = None
    overall_confidence: Literal["high", "medium", "low", "unknown"] = "unknown"
    gaps: list[str] = Field(default_factory=list)  # ["revenue_by_channel", ...]
    contradictory_sources: list[str] = Field(
        default_factory=list,
        description="Notes on sources that disagree (e.g. 'Crunchbase says $5M, TechCrunch says $7M').",
    )
    human_reviewed: bool = False
    human_reviewer: str | None = None
    human_review_notes: str | None = None
