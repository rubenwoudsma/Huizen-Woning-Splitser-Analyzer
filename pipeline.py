from __future__ import annotations

import math
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import yaml
from shapely.geometry import Point


CBS_BASE = "https://datasets.cbs.nl/odata/v1/CBS"
BAG_BASE = "https://api.pdok.nl/kadaster/bag/ogc/v2"
LOC_BASE = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
KEA_WMS = "https://apps.geodan.nl/public/data/org/gws/YWFMLMWERURF/kea_public/wms"


def load_config(path: str = "params.yml") -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def cbs_table(table_id: str) -> pd.DataFrame:
    url = f"{CBS_BASE}/{table_id}/TypedDataSet"
    rows = []
    while url:
        res = requests.get(url, timeout=60)
        res.raise_for_status()
        js = res.json()
        rows.extend(js.get("value", []))
        url = js.get("@odata.nextLink")
    return pd.DataFrame(rows)


def pdok_items(collection: str, bbox: list[float], limit: int = 1000) -> gpd.GeoDataFrame:
    url = f"{BAG_BASE}/collections/{collection}/items"
    params = {"f": "json", "bbox": ",".join(map(str, bbox)), "limit": limit}
    feats = []
    while url:
        res = requests.get(url, params=params if "?" not in url else None, timeout=60)
        res.raise_for_status()
        js = res.json()
        feats.extend(js.get("features", []))
        nxt = None
        for link in js.get("links", []):
            if link.get("rel") == "next":
                nxt = link.get("href")
                break
        url = nxt
        params = None
    return gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")


def loc_free(q: str, fq: str | None = None, rows: int = 1) -> dict:
    params = {"q": q, "rows": rows}
    if fq:
        params["fq"] = fq
    res = requests.get(f"{LOC_BASE}/free", params=params, timeout=60)
    res.raise_for_status()
    return res.json()


def huizen_bbox() -> list[float]:
    doc = loc_free("Huizen", fq="type:gemeente", rows=1)["response"]["docs"][0]
    bbox = doc["bbox"].replace("BOX(", "").replace(")", "").split(",")
    xmin, ymin = [float(x) for x in bbox[0].split()]
    xmax, ymax = [float(x) for x in bbox[1].split()]
    return [xmin, ymin, xmax, ymax]


def download_wijkbuurtkaart(url: str, out_zip: Path) -> Path:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if not out_zip.exists():
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        out_zip.write_bytes(r.content)
    with zipfile.ZipFile(out_zip, "r") as zf:
        gpkg = [n for n in zf.namelist() if n.lower().endswith(".gpkg")][0]
        zf.extract(gpkg, out_zip.parent)
        return out_zip.parent / gpkg


def detect_buurt_layer(gpkg_path: Path) -> str:
    layers = gpd.list_layers(gpkg_path)
    for _, row in layers.iterrows():
        if "buurt" in str(row["name"]).lower():
            return str(row["name"])
    return str(layers.iloc[0]["name"])

def geocode_locatieserver(query: str) -> Point | None:
    res = requests.get(
        f"{LOC_BASE}/free",
        params={"q": query, "fq": "type:adres", "rows": 1, "fl": "centroide_ll"},
        timeout=30,
    )
    res.raise_for_status()
    docs = res.json().get("response", {}).get("docs", [])
    if not docs:
        return None

    ll = docs[0].get("centroide_ll")
    if not ll:
        return None

    coords = ll.replace("POINT(", "").replace(")", "").split()
    lon, lat = map(float, coords)
    return Point(lon, lat)

def normalize_buurten(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    rename = {}
    for c in gdf.columns:
        low = c.lower()
        if low in {"bu_code", "buurtcode"}:
            rename[c] = "buurtcode"
        elif low in {"wk_code", "wijkcode"}:
            rename[c] = "wijkcode"
        elif low in {"gm_naam", "gemeentenaam"}:
            rename[c] = "gemeentenaam"
        elif low in {"bu_naam", "buurtnaam"}:
            rename[c] = "buurtnaam"
        elif low in {"wk_naam", "wijknaam"}:
            rename[c] = "wijknaam"
    return gdf.rename(columns=rename)


def normalize_bag(vbo: gpd.GeoDataFrame, adr: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cols = {c.lower(): c for c in vbo.columns}
    oppervlakte = cols.get("oppervlakte") or next(c for c in vbo.columns if "oppervlakte" in c.lower())
    gebruik = cols.get("gebruiksdoelen") or next((c for c in vbo.columns if "gebruiksdoel" in c.lower()), None)
    addr_key = next((c for c in vbo.columns if "hoofdadres" in c.lower() or "nummeraanduid" in c.lower()), None)

    out = vbo.copy()
    out["oppervlakte_m2"] = pd.to_numeric(out[oppervlakte], errors="coerce")
    if gebruik:
        out = out[out[gebruik].astype(str).str.lower().str.contains("woon", na=False)].copy()
    out["bag_address_key"] = out[addr_key].astype(str) if addr_key else out["id"].astype(str)

    akey = next((c for c in adr.columns if "adresseerbaarobject" in c.lower() or "nummeraanduid" in c.lower()), "id")
    adr2 = adr.copy()
    adr2["bag_address_key"] = adr2[akey].astype(str)

    keep = ["bag_address_key", "geometry"]
    for c in adr2.columns:
        low = c.lower()
        if low in {"postcode", "huisnummer"} or "woonplaats" in low or "straat" in low or "openbareruimte" in low:
            keep.append(c)
    merged = out.merge(adr2[keep].drop(columns="geometry", errors="ignore"), on="bag_address_key", how="left")
    merged["adres_id"] = merged["bag_address_key"]
    return merged


def parse_1200_list(path: Path, snapshot_date: str) -> pd.DataFrame:
    import camelot

    cols = ["benaming", "locatie", "aantal_raw", "soort_ontwikkeling", "status_raw", "afgerond_in_aanbouw"]
    tables = camelot.read_pdf(str(path), pages="all", flavor="stream")
    frames = []
    for t in tables:
        df = t.df.copy()
        while df.shape[1] < 6:
            df[df.shape[1]] = ""
        df = df.iloc[:, :6]
        df.columns = cols
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)

    rows = []
    cur = None
    for _, r in raw.iterrows():
        rr = {k: str(r[k]).replace("\n", " ").strip() for k in cols}
        start = bool(rr["benaming"]) and (any(ch.isdigit() for ch in rr["aantal_raw"]) or rr["aantal_raw"].upper() == "PM")
        if start:
            if cur:
                rows.append(cur)
            cur = rr
        else:
            if cur is None:
                cur = rr
            else:
                for k in cols:
                    if rr[k]:
                        cur[k] = f"{cur[k]} {rr[k]}".strip()
    if cur:
        rows.append(cur)

    out = pd.DataFrame(rows)
    out["snapshot_date"] = snapshot_date
    out["is_pm"] = out["aantal_raw"].str.upper().eq("PM")
    return out


def count_mid(value: str) -> float | None:
    if value is None:
        return None
    s = str(value).replace("–", "-").strip()
    if s.upper() == "PM" or not s:
        return None
    if s.isdigit():
        return float(s)
    if "-" in s:
        lo, hi = s.split("-", 1)
        lo, hi = lo.strip(), hi.strip()
        if lo.isdigit() and hi.isdigit():
            return (float(lo) + float(hi)) / 2.0
    return None


def status_bucket(status_raw: str, started_raw: str) -> str:
    text = f"{status_raw or ''} {started_raw or ''}".lower()
    if "afgerond" in text:
        return "afgerond"
    if "start bouw" in text or "werkzaamheden gestart" in text:
        return "gestart"
    if "vergunning" in text or "aanvraag" in text:
        return "vergunning"
    if "geen ontwikkelingen" in text or "ligt bij initiatiefnemer" in text or "gebiedsvisie" in text:
        return "zacht"
    if "in voorbereiding" in text or "besluitvorming" in text:
        return "voorbereiding"
    return "onbekend"


def p_le_2_public(candidates: pd.DataFrame, buurt_stats: pd.DataFrame, share_le2_muni: float = 0.64) -> pd.DataFrame:
    df = candidates.merge(buurt_stats, on="buurtcode", how="left")
    one_idx = (df["share_one_person_buurt"].fillna(df["share_one_person_buurt"].mean()) /
               max(df["share_one_person_buurt"].mean(), 1e-6)).clip(0.2, 2.0)
    age_idx = (df["share_65_plus_buurt"].fillna(df["share_65_plus_buurt"].mean()) /
               max(df["share_65_plus_buurt"].mean(), 1e-6)).clip(0.2, 2.0)
    house_idx = (df["share_eengezins_buurt"].fillna(df["share_eengezins_buurt"].mean()) /
                 max(df["share_eengezins_buurt"].mean(), 1e-6)).clip(0.2, 2.0)
    df["p_le_2"] = (share_le2_muni * (0.4 * one_idx + 0.3 * age_idx + 0.3 * house_idx)).clip(0.05, 0.95)
    return df


def split_analysis(candidates: pd.DataFrame, min_total_m2: float = 120, min_unit_m2: float = 50,
                   net_efficiency: float = 0.9, adoption_rate: float = 0.10) -> pd.DataFrame:
    df = candidates.copy()
    df = df[df["oppervlakte_m2"] >= min_total_m2].copy()
    df["netto_splitsbaar_m2"] = df["oppervlakte_m2"] * net_efficiency
    df["max_units_after_split"] = (df["netto_splitsbaar_m2"] / min_unit_m2).apply(math.floor).clip(upper=2)
    df["split_feasible"] = df["max_units_after_split"] >= 2
    df["units_added_if_split"] = df["max_units_after_split"] - 1
    df["expected_units_added"] = df["units_added_if_split"] * df["p_le_2"] * adoption_rate
    return df


def main() -> None:
    cfg = load_config("params.yml")
    out = Path("data/processed")
    out.mkdir(parents=True, exist_ok=True)

    bbox = huizen_bbox()

    gpkg = download_wijkbuurtkaart(cfg["cbs"]["geometry_zip_url"], Path(cfg["paths"]["geometry_zip"]))
    buurten = gpd.read_file(gpkg, layer=detect_buurt_layer(gpkg))
    buurten = normalize_buurten(buurten)
    buurten = buurten[buurten["gemeentenaam"].astype(str).str.lower().eq("huizen")].copy()

    buurten_4326 = buurten.to_crs(4326)
    buurten_4326.to_file(out / "buurten_huizen.geojson", driver="GeoJSON")
    
    kwb = cbs_table(cfg["cbs"]["kwb_table"])
    kwb = kwb[kwb["Gemeentenaam_1"].astype(str).str.lower().eq("huizen")].copy()
    kwb = kwb[kwb["SoortRegio_2"].astype(str).str.contains("buurt", case=False, na=False)].copy()
    buurt_stats = pd.DataFrame({
        "buurtcode": kwb["Codering_3"].astype(str),
        "share_one_person_buurt": pd.to_numeric(kwb["Eenpersoonshuishoudens_28"], errors="coerce") /
                                  pd.to_numeric(kwb["HuishoudensTotaal_27"], errors="coerce"),
        "share_65_plus_buurt": pd.to_numeric(kwb["65JaarOfOuder_9"], errors="coerce") /
                               pd.to_numeric(kwb["AantalInwoners_5"], errors="coerce"),
        "share_eengezins_buurt": pd.to_numeric(kwb["PercentageEengezinswoning_40"], errors="coerce") / 100.0,
    })

    vbo = pdok_items("verblijfsobject", bbox)
    adr = pdok_items("adres", bbox)
    bag = normalize_bag(vbo, adr)
    bag = gpd.GeoDataFrame(bag, geometry="geometry", crs="EPSG:4326")
    bag = gpd.sjoin(bag, buurten[["buurtcode", "wijkcode", "geometry"]], how="left", predicate="within")

    candidates = p_le_2_public(bag.drop(columns="index_right", errors="ignore"), buurt_stats)
    candidates = split_analysis(candidates)
    candidates_gdf = gpd.GeoDataFrame(candidates, geometry="geometry", crs="EPSG:4326")
    candidates_gdf.to_file(out / "split_candidates_public.geojson", driver="GeoJSON")
    candidates.to_csv(out / "split_candidates_public.csv", index=False)

    by_buurt = (candidates.groupby("buurtcode", dropna=False)
                .agg(candidate_addresses=("adres_id", "nunique"),
                     expected_units_added=("expected_units_added", "sum"))
                .reset_index())
    by_buurt.to_csv(out / "split_potential_buurt_public.csv", index=False)

    path_1200 = Path(cfg["paths"]["wimra_input_path"])
if path_1200.exists():
    w1200 = parse_1200_list(path_1200, snapshot_date="2025-05-22")
    w1200["aantal_mid"] = w1200["aantal_raw"].apply(count_mid)
    w1200["status_bucket"] = w1200.apply(
        lambda r: status_bucket(r["status_raw"], r["afgerond_in_aanbouw"]),
        axis=1,
    )
    w1200.to_csv(out / "wimra_1200_list_normalized.csv", index=False)

    # realisatie-samenvatting
    realisatie = (
        w1200.assign(woningaantal=w1200["aantal_mid"].fillna(0))
        .groupby("status_bucket", dropna=False, as_index=False)["woningaantal"]
        .sum()
    )
    realisatie.to_csv(out / "wimra_realisatiegraad_summary.csv", index=False)

    # simpele geocodering op adresachtige locaties
    w1200["zoekquery"] = (
        w1200["locatie"].fillna("").astype(str).str.strip() + ", Huizen"
    )
    w1200["geometry"] = w1200["zoekquery"].apply(geocode_locatieserver)
    projects_gdf = gpd.GeoDataFrame(w1200, geometry="geometry", crs="EPSG:4326")
    projects_gdf = projects_gdf[projects_gdf["geometry"].notna()].copy()
    projects_gdf.to_file(out / "wimra_1200_list_geocoded.geojson", driver="GeoJSON")


if __name__ == "__main__":
    main()
