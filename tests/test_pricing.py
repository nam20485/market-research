import pytest

from app.services.pricing import build_pricing_strategy, condition_multiplier


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("new", 1.10),
        ("New", 1.10),
        ("  NEW  ", 1.10),
        ("like-new", 1.0),
        ("Like New", 1.0),
        ("like_new", 1.0),
        ("good", 0.90),
        ("GOOD", 0.90),
        ("fair", 0.75),
        ("poor", 0.60),
    ],
)
def test_condition_multiplier_matches_table(condition: str, expected: float) -> None:
    assert condition_multiplier(condition) == expected


@pytest.mark.parametrize("condition", [None, "", "mint", "refurbished"])
def test_condition_multiplier_defaults_to_one_for_unknown(condition: str | None) -> None:
    assert condition_multiplier(condition) == 1.0


def test_build_pricing_strategy_computes_listing_and_floor() -> None:
    strategy = build_pricing_strategy(
        100.0,
        haggle_pct=0.15,
        floor_pct=0.10,
        condition="good",
        confidence="sold_comps",
    )

    assert strategy.fmv == 100.0
    # listing_price = 100 * 1.15 * 0.90 = 103.5
    assert strategy.listing_price == 103.5
    # firm_bottom = 100 * 0.90 * 0.90 = 81.0
    assert strategy.firm_bottom == 81.0
    assert strategy.condition_multiplier == 0.90
    assert strategy.haggle_pct == 0.15
    assert strategy.floor_pct == 0.10
    assert strategy.confidence == "sold_comps"
    assert strategy.currency == "USD"
    assert strategy.rationale is None


def test_build_pricing_strategy_defaults_multiplier_for_unknown_condition() -> None:
    strategy = build_pricing_strategy(
        200.0,
        haggle_pct=0.20,
        floor_pct=0.05,
        condition=None,
        confidence="asking_price",
    )

    assert strategy.condition_multiplier == 1.0
    assert strategy.listing_price == 240.0
    assert strategy.firm_bottom == 190.0


def test_build_pricing_strategy_rounds_money_to_two_decimals() -> None:
    strategy = build_pricing_strategy(
        33.333,
        haggle_pct=0.1234,
        floor_pct=0.0987,
        condition="fair",
        confidence="unknown",
        rationale="insufficient data",
    )

    assert strategy.fmv == round(33.333, 2)
    assert strategy.listing_price == round(33.333 * 1.1234 * 0.75, 2)
    assert strategy.firm_bottom == round(33.333 * (1 - 0.0987) * 0.75, 2)
    assert strategy.rationale == "insufficient data"


def test_build_pricing_strategy_carries_custom_currency() -> None:
    strategy = build_pricing_strategy(
        50.0,
        haggle_pct=0.1,
        floor_pct=0.1,
        condition="new",
        confidence="sold_comps",
        currency="EUR",
    )

    assert strategy.currency == "EUR"
