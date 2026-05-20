DECOMPOSITION_PROMPT_VERSION = "v4"

DECOMPOSITION_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reason_type": {
            "type": "string",
            "enum": [
                "business_performance",
                "valuation",
                "macro_theme",
                "income",
                "portfolio_role",
                "behavioral",
                "social_proof",
                "constraint_based",
                "mixed",
                "unclear",
            ],
        },
        "monitorability": {
            "type": "string",
            "enum": ["high", "medium", "low"],
        },
        "decomposition_confidence": {
            "type": "number",
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim_text": {"type": "string"},
                    "claim_type": {
                        "type": "string",
                        "enum": [
                            "growth",
                            "margins",
                            "demand",
                            "valuation",
                            "cash_flow",
                            "income",
                            "macro_tailwind",
                            "portfolio_fit",
                            "other",
                        ],
                    },
                    "confidence": {"type": "number"},
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "entity_name": {"type": "string"},
                                "entity_ticker": {"type": ["string", "null"]},
                                "entity_type": {
                                    "type": "string",
                                    "enum": [
                                        "held_company",
                                        "supplier",
                                        "customer",
                                        "competitor",
                                        "benchmark",
                                        "macro_series",
                                        "commodity",
                                        "sector_proxy",
                                        "other",
                                    ],
                                },
                                "relation_type": {
                                    "type": "string",
                                    "enum": [
                                        "depends_on",
                                        "validated_by",
                                        "threatened_by",
                                        "compared_against",
                                    ],
                                },
                                "rationale": {"type": "string"},
                                "confidence": {"type": "number"},
                                "confirmation_required": {"type": "boolean"},
                                "signals": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "signal_type": {
                                                "type": "string",
                                                "enum": [
                                                    "price_move",
                                                    "revenue_growth",
                                                    "earnings_growth",
                                                    "guidance_change",
                                                    "earnings_surprise",
                                                    "transcript_topic",
                                                    "news_topic",
                                                    "insider_transaction",
                                                    "dividend_change",
                                                    "macro_series_change",
                                                ],
                                            },
                                            "signal_label": {"type": "string"},
                                            "signal_config_json": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "metric": {"type": "string"},
                                                    "operator": {"type": "string", "enum": [">=", "<=", ">", "<", "=="]},
                                                    "threshold": {"type": "number"},
                                                    "threshold_pct": {"type": "number"},
                                                    "segment": {"type": "string"},
                                                    "topic": {"type": "string"},
                                                },
                                                "required": [],
                                            },
                                            "rationale": {"type": "string"},
                                            "confidence": {"type": "number"},
                                            "confirmation_required": {"type": "boolean"},
                                        },
                                        "required": [
                                            "signal_type",
                                            "signal_label",
                                            "signal_config_json",
                                            "rationale",
                                            "confidence",
                                            "confirmation_required",
                                        ],
                                    },
                                },
                            },
                            "required": [
                                "entity_name",
                                "entity_ticker",
                                "entity_type",
                                "relation_type",
                                "rationale",
                                "confidence",
                                "confirmation_required",
                                "signals",
                            ],
                        },
                    },
                },
                "required": [
                    "claim_text",
                    "claim_type",
                    "confidence",
                    "entities",
                ],
            },
        },
    },
    "required": [
        "reason_type",
        "monitorability",
        "decomposition_confidence",
        "claims",
    ],
}

DECOMPOSITION_SYSTEM_PROMPT = """You decompose an investor's reason for owning a holding into monitorable claims, entities, and signals.

Return only schema-conforming JSON (no extra keys, no prose). Be concise: keep every rationale field under 20 words, signal_label under 8 words.

Rules:
- If the reason contains any investment rationale (even one sentence with a measurable premise), extract at least one claim. Zero claims is only acceptable if the entire text is purely descriptive with zero investment intent (e.g. "they make phones").
- Extract claims from all three fields: why_own_it, must_remain_true, and what_would_change_my_mind. Conditions in must_remain_true and what_would_change_my_mind are often the most monitorable.
- Do not create monitorable signals from pure description with no investment intent.
- Do not invent numeric thresholds unless the user text clearly implies them.
- Do not assume proxy entities unless there is a plausible causal relationship.
- Mark speculative mappings with lower confidence and confirmation_required=true.
- Entities and signals within a claim may be empty arrays if the claim is too vague to generate them, but the claim itself must still be captured.
- Limit to the 3 most important claims, 3 entities per claim, 3 signals per entity. Quality over quantity.
"""

DECOMPOSITION_USER_PROMPT = """Holding
- Ticker: {ticker}
- Name: {name}

User reason
- Why I own it: {why_own_it}
- What must remain true: {must_remain_true}
- What would change my mind: {what_would_change_my_mind}
"""


def build_decomposition_prompt(payload: dict) -> str:
    return DECOMPOSITION_USER_PROMPT.format(
        ticker=payload["ticker"],
        name=payload["name"],
        why_own_it=payload["why_own_it"],
        must_remain_true=payload.get("must_remain_true") or "None provided",
        what_would_change_my_mind=payload.get("what_would_change_my_mind") or "None provided",
    )
