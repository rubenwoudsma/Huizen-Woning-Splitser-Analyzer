from __future__ import annotations

import math
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

CBS_URL = "https://geodata.cbs.nl/files/Wijkenbuurtkaart/WijkBuurtkaart_2024_v2.zip"
BAG_URL = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/verblijfsobject/items"


def load_cbs_buurten():
    zip_path = Path("data/raw/cbs.zip")
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    if not zip_path.exists():
        r = requests.get(CBS_URL)
        zip_path.write_bytes(r.content)

    with zipfile.ZipFile(zip_path, "r") as z:
        gpkg = [f for f in z.namelist() if f.endswith(".gpkg")][0]
        z.extract(gpkg, zip_path.parent)

    gdf = gpd.read_file(zip_path.parent / gpkg, layer="buurten")
    gdf.columns = [c.lower() for c in gdf.columns]

    gdf["gemeente"] = gdf.get("gm_naam", gdf.get("gemeentenaam"))
    gdf = gdf[gdf["gemeente"].str.lower().str.strip() == "huizen"]

    if "bu_code" in gdf.columns:
        gdf = gdf.rename(columns={"bu_code": "buurtcode"})
    if "bu_naam" in gdf.columns:
        gdf = gdf.rename(columns={"bu_naam": "buurtnaam"})

    gdf = gdf[["buurtcode", "buurtnaam", "geometry"]]
    gdf = gdf.to_crs(4326)

    gdf["geometry"] = gdf["geometry"].simplify(0.0005)

    return gdf


def get_bag_huizen():
    bbox = [5.15, 52.25, 5.35, 52.35]

    params = {"bbox": ",".join(map(str, bbox)), "limit": 1000, "f": "json"}
    url = BAG_URL
    features = []

    while url:
        r = requests.get(url, params=params if "?" not in url else None)
        data = r.json()

        features.extend(data["features"])

        url = next((l["href"] for l in data["links"] if l["rel"] == "next"), None)
        params = None

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")

    if "gebruiksdoelen" in gdf.columns:
        gdf = gdf[
            gdf["gebruiksdoelen"].astype(str).str.contains("woon", case=False)
            & ~gdf["gebruiksdoelen"].astype(str).str.contains("bedrijf|kantoor", case=False)
        ]

    gdf["oppervlakte_m2"] = pd.to_numeric(gdf["oppervlakte"], errors="coerce")

    return gdf[["geometry", "oppervlakte_m2"]]


def split_analysis(df, min_total_m2=120, min_unit_m2=50):
    df = df[df["oppervlakte_m2"] >= min_total_m2].copy()

    df["p_le_2"] = (0.3 + 0.002 * (df["oppervlakte_m2"] - 80)).clip(0.2, 0.9)

    df["units_added_if_split"] = 1
    df["expected_units_added"] = df["units_added_if_split"] * df["p_le_2"] * 0.10

    return df


def load_1200_list(path):
    try:
        df = pd.read_csv(path)
    except:
        try:
            df = pd.read_csv(path, sep=";")
        except:
            df = pd.read_excel(path)

    df.columns = [c.lower() for c in df.columns]

    df = df[~df["locatie"].str.contains("totaal", na=False)]

    return df


def geocode(query):
    try:
        r = requests.get(
            "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free",
            params={"q": query, "rows": 1, "fl": "centroide_ll"},
        )
        docs = r.json()["response"]["docs"]

        if not docs:
            return None

        lon, lat = map(float, docs[0]["centroide_ll"].replace("POINT(", "").replace(")", "").split())
        return Point(lon, lat)

    except:
        return None


def main():
    out = Path("data/processed")
    out.mkdir(parents=True, exist_ok=True)

    buurten = load_cbs_buurten()
    buurten.to_file(out / "buurten_huizen.geojson")

    houses = get_bag_huizen()

    houses = gpd.sjoin(houses, buurten, predicate="within")
    houses = houses[houses["buurtcode"].notna()]

    candidates = split_analysis(houses)

    candidates.to_file(out / "split_candidates_public.geojson")
    candidates.drop(columns="geometry").to_csv(out / "split_candidates_public.csv")

    by_buurt = candidates.groupby("buurtcode")["expected_units_added"].sum().reset_index()
    by_buurt.to_csv(out / "split_potential_buurt_public.csv", index=False)

    path = Path("data/raw/1-200-lijst-in-excel.xlsx")

    if path.exists():
        df = load_1200_list(path)
        df["geometry"] = df["locatie"].apply(lambda x: geocode(f"{x}, Huizen"))

        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        gdf = gdf[gdf["geometry"].notna()]

        gdf = gpd.sjoin(gdf, buurten, predicate="within")

        gdf.to_file(out / "wimra_1200_list.geojson")


if __name__ == "__main__":
    main()
