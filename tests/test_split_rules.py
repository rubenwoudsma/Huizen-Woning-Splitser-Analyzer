import pandas as pd

from src.pipeline import split_analysis


def test_split_analysis_basic():
    df = pd.DataFrame(
        {
            "adres_id": ["a1", "a2", "a3"],
            "oppervlakte_m2": [140, 119, 210],
            "p_le_2": [0.8, 0.7, 0.6],
        }
    )
    out = split_analysis(df, min_total_m2=120, min_unit_m2=50, net_efficiency=0.9, adoption_rate=0.10)

    assert set(out["adres_id"]) == {"a1", "a3"}
    assert (out["split_feasible"]).all()
    assert (out["units_added_if_split"] >= 1).all()
    assert (out["expected_units_added"] > 0).all()
