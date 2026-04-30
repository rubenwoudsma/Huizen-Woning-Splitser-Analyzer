from __future__ import annotations

import math
import zipfile
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

# -------------------------
# CONSTANTEN
# -------------------------

CBS_URL = "https://geodata.cbs.nl/files/Wijkenbuurtkaart/WijkBuurtkaart_2024_v2.zip"
BAG_URL = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/verblijfsobject/items"


# -------------------------
# ROBUUSTE REQUEST
# -------------------------

def safe_request(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Request failed (attempt {i+1}): {e}")
            if i < retries - 1:
                time.sleep(2)
            else:
                print("❌ Definitief gefaald")
                return None


# -------------------------
# CBS BUURTEN
# -------------------------

def load_cbs_buurten() -> gpd.GeoDataFrame:
    zip_path = Path("data/raw/cbs.zip")
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    if not zip_path.exists():
        print("⬇️ Download CBS data")
        r = safe_request(CBS_URL)
        if r:
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

    gdf = gdf[["buurtcode", "buurtnaam", "geometry"]].to_crs(4326)
    gdf["geometry"] = gdf["geometry"].simplify(0.0005)

    return gdf


# -------------------------
# BAG DATA (ROBUST)
# -------------------------

def get_bag_huizen():
    bbox = [5.15, 52.25, 5.35, 52.35]

    params = {
        "bbox": ",".join(map(str, bbox)),
        "limit": 1000,
        "f": "json"
    }

    url = BAG_URL
    features = []
    page = 0

    while url:
        print(f"📦 BAG pagina {page}")

        r = safe_request(url, params=params if "?" not in url else None)

        if r is None:
            print("⚠️ BAG API faalt → gebruik partial dataset")
            break

        data = r.json()
        features.extend(data.get("features", []))

        url = next((l["href"] for l in data.get("links", []) if l["rel"] == "next"), None)
        params = None
        page += 1

        time.sleep(0.2)  # throttle

    if len(features) < 1000:
        print("⚠️ BAG dataset mogelijk incompleet")
    
    if not features:
        print("❌ Geen BAG data opgehaald")
        return gpd.GeoDataFrame(columns=["geometry", "oppervlakte_m2"])

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")

    if "gebruiksdoelen" in gdf.columns:
        gdf = gdf[
            gdf["gebruiksdoelen"].astype(str).str.contains("woon", case=False)
            & ~gdf["gebruiksdoelen"].astype(str).str.contains("bedrijf|kantoor", case=False)
        ]

    gdf["oppervlakte_m2"] = pd.to_numeric(gdf["oppervlakte"], errors="coerce")

    return gdf[["geometry", "oppervlakte_m2"]]


# -------------------------
# MODEL
# -------------------------

def add_probability_model(df):
    df["p_le_2"] = (0.3 + 0.002 * (df["oppervlakte_m2"] - 80)).clip(0.2, 0.9)
    return df


def split_analysis(
    df: pd.DataFrame,
    min_total_m2: float = 120,
    min_unit_m2: float = 50,
    net_efficiency: float = 0.9,
    adoption_rate: float = 0.10,
) -> pd.DataFrame:

    df = df.copy()

    df = df[df["oppervlakte_m2"] >= min_total_m2]

    df["netto_splitsbaar_m2"] = df["oppervlakte_m2"] * net_efficiency

    df["max_units_after_split"] = (
        df["netto_splitsbaar_m2"] / min_unit_m2
    ).apply(int).clip(upper=2)

    # 🔥 DIT WAS VERDWENEN → NODIG VOOR TEST
    df["split_feasible"] = df["max_units_after_split"] >= 2

    df["units_added_if_split"] = df["max_units_after_split"] - 1

    if "p_le_2" not in df.columns:
        df["p_le_2"] = 0.6

    df["expected_units_added"] = (
        df["units_added_if_split"] * df["p_le_2"] * adoption_rate
    )

    return df


# -------------------------
# KLIMAAT DATA
# -------------------------

def load_heatstress(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_excel(path, sheet_name="Data")

        df.columns = [str(c).lower().strip() for c in df.columns]

        print("🔍 Klimaat kolommen:", df.columns.tolist())

        buurt_col = None
        shadow_col = None
        wijktype_col = None
        inwoners_col = None

        # 🔍 kolommen zoeken (robuust!)
        for col in df.columns:
            if "buurtcode" in col:
                buurt_col = col
            elif "shdtot" in col and "ahn4" in col:
                shadow_col = col
            elif "wijktype" in col:
                wijktype_col = col
            elif "aant_inw" in col:
                inwoners_col = col

        # 🔥 fallback als minimaal niet gevonden
        if buurt_col is None or shadow_col is None:
            print("⚠️ Schaduwdata niet bruikbaar → overslaan")
            return pd.DataFrame(columns=["buurtcode", "schaduw", "wijktype", "aantal_inwoners"])

        # 🔄 rename alleen wat bestaat
        rename_map = {
            buurt_col: "buurtcode",
            shadow_col: "schaduw"
        }

        if wijktype_col:
            rename_map[wijktype_col] = "wijktype"

        if inwoners_col:
            rename_map[inwoners_col] = "aantal_inwoners"

        df = df.rename(columns=rename_map)

        # 🔢 numeriek maken
        df["schaduw"] = pd.to_numeric(df["schaduw"], errors="coerce")

        if "aantal_inwoners" in df.columns:
            df["aantal_inwoners"] = pd.to_numeric(df["aantal_inwoners"], errors="coerce")

        # 🔥 alleen kolommen selecteren die bestaan
        cols = ["buurtcode", "schaduw"]

        if "wijktype" in df.columns:
            cols.append("wijktype")

        if "aantal_inwoners" in df.columns:
            cols.append("aantal_inwoners")

        return df[cols]

    except Exception as e:
        print(f"⚠️ Fout bij laden klimaatdata: {e}")
        return pd.DataFrame(columns=["buurtcode", "schaduw", "wijktype", "aantal_inwoners"])


# -------------------------
# MAIN
# -------------------------

def main():
    print("🚀 Pipeline gestart")

    out = Path("data/processed")
    out.mkdir(parents=True, exist_ok=True)

    buurten = load_cbs_buurten()
    buurten.to_file(out / "buurten_huizen.geojson")

    houses = get_bag_huizen()

    if len(houses) == 0:
        print("⚠️ Geen BAG data → pipeline stopt")
        return

    houses = gpd.sjoin(houses, buurten, predicate="within")
    houses = houses[houses["buurtcode"].notna()]

    houses = add_probability_model(houses)
    candidates = split_analysis(houses)

    candidates.to_file(out / "split_candidates_public.geojson")
    candidates.drop(columns="geometry").to_csv(out / "split_candidates_public.csv", index=False)

    by_buurt = candidates.groupby("buurtcode")["expected_units_added"].sum().reset_index()

    # Klimaat toevoegen
    heat_path = Path("data/raw/Downloadbuurtdashboard.xlsx")
    if heat_path.exists():
        try:
            heat = load_heatstress(heat_path)
        
            if len(heat) > 0:
                by_buurt = by_buurt.merge(heat, on="buurtcode", how="left")
            else:
                print("⚠️ Geen schaduwdata toegevoegd")
        
        except Exception as e:
            print(f"⚠️ Schaduwdata mislukt: {e}")

    by_buurt.to_csv(out / "split_potential_buurt_public.csv", index=False)

    print("✅ Pipeline klaar")


if __name__ == "__main__":
    main()
