from app.services.signal_quality import cap_claim_signals, filter_signal_payloads, prepare_signal


def test_prepare_signal_makes_generic_labels_search_ready_and_infers_threat_direction():
    signal = prepare_signal(
        {
            "signal_type": "revenue_growth",
            "signal_label": "Revenue growth",
            "rationale": "Growth supports the case.",
            "confidence": 0.8,
        },
        claim_text="NVDA data center demand keeps growing",
        source_field="what_would_change_my_mind",
        entity_name="NVIDIA",
        entity_ticker="NVDA",
        entity_type="held_company",
        relation_type="validated_by",
    )

    assert signal["signal_label"] == "NVDA Revenue growth"
    assert signal["direction"] == "threatens"
    assert signal["evidence_scope"] == "company"
    assert signal["materiality"] == "medium"
    assert signal["quality"]["status"] == "ready"


def test_filter_signal_payloads_dedupes_and_caps_each_claim():
    signals = [
        {
            "signal_type": "news_topic",
            "signal_label": "AMD AI competition",
            "signal_config_json": {"topic": "AMD AI competition"},
            "rationale": "Customer wins would pressure the moat.",
            "confidence": 0.9,
        },
        {
            "signal_type": "news_topic",
            "signal_label": "AMD AI competition",
            "signal_config_json": {"topic": "AMD AI competition"},
            "rationale": "Duplicate watch should not be created.",
            "confidence": 0.9,
        },
    ] + [
        {
            "signal_type": "price_move",
            "signal_label": f"NVDA price move {index}",
            "signal_config_json": {"threshold_pct": index},
            "rationale": "A sharp move should prompt a review.",
            "confidence": 0.5,
        }
        for index in range(1, 8)
    ]

    filtered = filter_signal_payloads(
        signals,
        claim_text="NVDA keeps its AI advantage",
        source_field="must_remain_true",
        entity_name="NVIDIA",
        entity_ticker="NVDA",
        entity_type="held_company",
        relation_type="validated_by",
        limit=5,
    )

    assert len(filtered) == 5
    assert len({(item["signal_type"], item["signal_label"]) for item in filtered}) == 5
    assert sum(item["signal_type"] == "news_topic" for item in filtered) == 1


def test_non_observable_signal_stays_review_only():
    signal = prepare_signal(
        {
            "signal_type": "news_topic",
            "signal_label": "NVDA moat",
            "signal_config_json": {"topic": "NVDA moat"},
            "rationale": "The moat remains strong.",
            "confidence": 0.95,
            "observable": False,
        },
        claim_text="NVDA maintains a durable moat",
        source_field="why_own_it",
        entity_name="NVIDIA",
        entity_ticker="NVDA",
        entity_type="held_company",
        relation_type="validated_by",
    )

    assert signal["quality"]["status"] == "review"
    assert "not_observable" in signal["quality"]["issues"]


def test_generic_conclusion_is_not_auto_ready_even_if_model_marks_it_observable():
    signal = prepare_signal(
        {
            "signal_type": "news_topic",
            "signal_label": "NVDA moat",
            "signal_config_json": {"topic": "NVDA moat"},
            "rationale": "The moat supports the case.",
            "confidence": 0.9,
            "observable": True,
        },
        claim_text="NVDA maintains a durable moat",
        source_field="why_own_it",
        entity_name="NVIDIA",
        entity_ticker="NVDA",
        entity_type="held_company",
        relation_type="validated_by",
    )

    assert signal["quality"]["status"] == "review"
    assert "not_specific" in signal["quality"]["issues"]


def test_cap_claim_signals_applies_limit_across_entities():
    entities = [
        {
            "entity_name": "NVIDIA",
            "signals": [
                {"signal_type": "revenue_growth", "signal_label": "NVDA revenue growth", "confidence": 0.9, "materiality": "high"},
                {"signal_type": "guidance_change", "signal_label": "NVDA guidance", "confidence": 0.8, "materiality": "medium"},
                {"signal_type": "earnings_surprise", "signal_label": "NVDA earnings surprise", "confidence": 0.7, "materiality": "medium"},
            ],
        },
        {
            "entity_name": "AMD",
            "signals": [
                {"signal_type": "news_topic", "signal_label": "AMD AI competition", "confidence": 0.9, "materiality": "high"},
                {"signal_type": "price_move", "signal_label": "AMD price move", "confidence": 0.5, "materiality": "low"},
                {"signal_type": "news_topic", "signal_label": "AMD AI competition", "confidence": 0.8, "materiality": "high"},
            ],
        },
    ]

    capped = cap_claim_signals(entities, limit=3)

    assert sum(len(entity["signals"]) for entity in capped) == 3
    labels = [signal["signal_label"] for entity in capped for signal in entity["signals"]]
    assert set(labels) == {"NVDA revenue growth", "AMD AI competition", "NVDA guidance"}
