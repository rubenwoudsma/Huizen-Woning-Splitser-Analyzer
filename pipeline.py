from __future__ import annotations

import random
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import yaml
from shapely.geometry import Point

CBS_GEO_URL = "https://geodata.cbs.nl/files/Wijkenbuurtkaart/WijkBuurtkaart_2024_v2.zip"


# -------------------------
# CONFIG
# -------------------------

def load_config(path: str = "params.yml") -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except Exception:
        return {}


# -------------------------
# DOWNLOAD CBS GEOMETRY
# -------------------------

def load_cbs_buurten() -> gpd.GeoDataFrame:
    zip_path = Path("data/raw/cbs.zip")
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    if not zip_path.exists():
        r = requests.get(CBS_GEO_URL, timeout=120)
        r.raise_for_status()
        zip_path.write_bytes(r.content)

    import zipfile
    with zipfile.ZipFile(zip_path, "r") as z:
        gpkg = [f for f in z.namelist() if f.endswith(".gpkg")][0]
        z.extract(gpkg, zip_path.parent)
        gpkg_path = zip_path.parent / gpkg

    gdf = gpd.read_file(gpkg_path)

    # normaliseer kolommen
    gdf.columns = [c.lower() for c in gdf.columns]

    return gdf


# -------------------------
# GENERATE FAKE HOUSES
# -------------------------

def generate_fake_houses(buurten: gpd.GeoDataFrame, n=200) -> gpd.GeoDataFrame:
    huizen = buurten.copy()

    points = []
    buurtcodes = []

    for _ in range(n):
        row = huizen.sample(1).iloc[0]
        poly = row.geometry

        if poly is None or poly.is_empty:
            continue

        minx, miny, maxx, maxy = poly.bounds

        for _ in range(10):
            p = Point(
                random.uniform(minx, maxx),
                random.uniform(miny, maxy)
            )
            if poly.contains(p):
                points.append(p)
                buurtcodes.append(row.get("bu_code") or row.get("buurtcode"))
                break

    df = pd.DataFrame({
        "adres_id": [f"a{i}" for i in range(len(points))],
        "oppervlakte_m2": [random.randint(80, 200) for _ in points],
        "p_le_2": [random.uniform(0.4, 0.9) for _ in points],
        "buurtcode": buurtcodes
    })

    return gpd.GeoDataFrame(df, geometry=points, crs="EPSG:4326")


# -------------------------
# SPLIT ANALYSIS
# -------------------------

def split_analysis(
    df: pd.DataFrame,
    min_total_m2: float = 120,
    min_unit_m2: float = 50,
    net_efficiency: float = 0.9,
    adoption_rate: float = 0.10,
) -> pd.DataFrame:

    df = df.copy()

    # filter op minimale grootte
    df = df[df["oppervlakte_m2"] >= min_total_m2]

    # simpele splitslogica (max 2 woningen)
    df["netto_splitsbaar_m2"] = df["oppervlakte_m2"] * net_efficiency
    df["max_units_after_split"] = (
        df["netto_splitsbaar_m2"] / min_unit_m2
    ).apply(int).clip(upper=2)

    df["split_feasible"] = df["max_units_after_split"] >= 2
    df["units_added"] = df["max_units_after_split"] - 1

    # fallback als p_le_2 ontbreekt
    if "p_le_2" not in df.columns:
        df["p_le_2"] = 0.6

    df["expected_units_added"] = (
        df["units_added"] * df["p_le_2"] * adoption_rate
    )

    return df


# -------------------------
# MAIN
# -------------------------

def main():
    print("Pipeline gestart")

    out = Path("data/processed")
    out.mkdir(parents=True, exist_ok=True)

    # -------------------------
    # CBS buurten laden
    # -------------------------

    buurten = load_cbs_buurten()

    # filter Huizen
    buurten = buurten[buurten["gm_naam"].str.lower() == "huizen"]

    buurten = buurten.to_crs(4326)

    buurten.rename(columns={"bu_code": "buurtcode"}, inplace=True)

    buurten.to_file(out / "buurten_huizen.geojson", driver="GeoJSON")

    print(f"Buurten geladen: {len(buurten)}")

    # -------------------------
    # fake woningen genereren
    # -------------------------

    houses = generate_fake_houses(buurten, n=300)

    print(f"Huizen gegenereerd: {len(houses)}")

    # -------------------------
    # analyse
    # -------------------------

    candidates = split_analysis(houses)

    # -------------------------
    # save outputs
    # -------------------------

    candidates.to_file(out / "split_candidates_public.geojson", driver="GeoJSON")
    candidates.drop(columns="geometry").to_csv(out / "split_candidates_public.csv", index=False)

    by_buurt = (
        candidates.groupby("buurtcode", as_index=False)["expected_units_added"]
        .sum()
    )

    by_buurt.to_csv(out / "split_potential_buurt_public.csv", index=False)

    print("Pipeline klaar")


if __name__ == "__main__":
    main()
