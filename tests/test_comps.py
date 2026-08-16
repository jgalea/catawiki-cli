import json

from cata.comps import MIN_SAMPLE, comparables
from cata.store import Store


def _insert(store, lot_id, price, brand="Omega", model="Speedmaster", category_id=333, sold=1):
    specs = json.dumps(
        [
            {"name": "Brand", "value": brand, "sid": 909, "vid": 1},
            {"name": "Model", "value": model, "sid": 966, "vid": 2},
        ]
    )
    store.connect().execute(
        """
        insert into lots (id, title, category_id, specs_json, sold, final_price, currency,
                          is_closed, outcome_recorded_at)
        values (?,?,?,?,?,?, 'EUR', 1, '2026-08-01T00:00:00+00:00')
        """,
        (lot_id, f"{brand} {model} {lot_id}", category_id, specs, sold, price if sold else None),
    )
    store.connect().commit()


def test_below_threshold_reports_insufficient(tmp_path):
    store = Store(tmp_path / "t.db")
    for i in range(3):
        _insert(store, i + 1, 10000 + i)
    result = comparables(store, category_id=333, brand="Omega", model="Speedmaster")
    assert result.sufficient is False
    assert result.sample_size == 3
    assert result.median is None


def test_median_and_quartiles_over_enough_samples(tmp_path):
    store = Store(tmp_path / "t.db")
    for i in range(MIN_SAMPLE + 2):
        _insert(store, i + 1, (i + 1) * 10000)
    result = comparables(store, category_id=333, brand="Omega", model="Speedmaster")
    assert result.sufficient is True
    assert result.sample_size == MIN_SAMPLE + 2
    assert result.median.amount > 0
    assert result.p25.amount <= result.median.amount <= result.p75.amount


def test_sell_through_counts_unsold(tmp_path):
    store = Store(tmp_path / "t.db")
    for i in range(MIN_SAMPLE):
        _insert(store, i + 1, 10000)
    for i in range(MIN_SAMPLE):
        _insert(store, 100 + i, None, sold=0)
    result = comparables(store, category_id=333, brand="Omega", model="Speedmaster")
    assert result.sell_through == 0.5


def test_falls_back_to_brand_when_model_has_no_samples(tmp_path):
    store = Store(tmp_path / "t.db")
    for i in range(MIN_SAMPLE):
        _insert(store, i + 1, 10000, model="Seamaster")
    result = comparables(store, category_id=333, brand="Omega", model="Speedmaster")
    assert result.sufficient is True
    assert result.basis == "category+brand"
