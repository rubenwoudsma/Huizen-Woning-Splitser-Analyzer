from __future__ import annotations

from pathlib import Path

import folium
from folium.plugins import MarkerCluster
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

PROCESSED = Path("data/processed")

st.set_page_config(page_title="Huizen Woningsplitsing Analyzer", layout="wide")


# -------------------------
# HELPERS
# -------------------------

def safe_lower(df):
    if df is None or len(df) == 0:
        return df
    df.columns = [c.lower() for c in df.columns]
    return df


def ensure_buurtcode(df):
    if df is None or len(df) == 0:
        return df

    if "buurtcode" in df.columns:
        return df

    if "bu_code" in df.columns:
        return df.rename(columns={"bu_code": "buurtcode"})

    return df


def clean_gdf_for_join(gdf):
    """Verwijder probleemkolommen voor spatial joins"""
    if gdf is None or len(gdf) == 0:
        return gdf

    gdf = gdf.copy()

    for col in ["index_left", "index_right"]:
        if col in gdf.columns:
            gdf = gdf.drop(columns=[col])

    return gdf


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        return pd.DataFrame()

    try:
        return safe_lower(pd.read_csv(path))
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_geojson(name: str):
    path = PROCESSED / name
    if not path.exists():
        return gpd.GeoDataFrame()

    try:
        return safe_lower(gpd.read_file(path))
    except Exception:
        return gpd.GeoDataFrame()


# -------------------------
# MAIN
# -------------------------

def main():
    # HEADER
    st.title("Huizen Woningsplitsing Analyzer")

    st.markdown(
        """
        Deze tool geeft inzicht in het **splitsingspotentieel van bestaande woningen**  
        en zet dit af tegen geplande woningbouw in de gemeente Huizen.

        Ontwikkeld door [Ruben Woudsma](https://rubenwoudsma.nl)
        """
    )

    st.info(
        "Deze analyse is indicatief en bedoeld om beleidskeuzes te ondersteunen, niet om exacte aantallen te voorspellen."
    )

    # -------------------------
    # DATA
    # -------------------------
    candidates = load_csv("split_candidates_public.csv")
    candidate_points = load_geojson("split_candidates_public.geojson")
    split_buurt = load_csv("split_potential_buurt_public.csv")
    buurten = load_geojson("buurten_huizen.geojson")
    projects = load_geojson("wimra_1200_list.geojson")

    buurten = ensure_buurtcode(buurten)
    split_buurt = ensure_buurtcode(split_buurt)

    # -------------------------
    # FILTERS
    # -------------------------
    col_filter, col_map = st.columns([1, 3])

    with col_filter:
        min_m2 = st.slider("Minimale woninggrootte (m²)", 80, 250, 120, 5)
        adoptie = st.slider("Adoptie splitsing (%)", 1, 30, 10)

    # filter kandidaten
    if len(candidates):
        candidates = candidates[candidates["oppervlakte_m2"] >= min_m2]

        candidates["expected_units_added"] = (
            candidates["units_added_if_split"]
            * candidates["p_le_2"]
            * (adoptie / 100)
        )

    if len(candidate_points):
        candidate_points = candidate_points[
            candidate_points["oppervlakte_m2"] >= min_m2
        ]

    # -------------------------
    # KPI'S
    # -------------------------
    k1, k2, k3 = st.columns(3)

    k1.metric("Kandidaat-adressen", int(len(candidates)))

    k2.metric(
        "Verwachte extra woningen",
        round(float(candidates["expected_units_added"].sum()), 1)
        if len(candidates) else 0
    )

    k3.metric(
        "Buurten met potentieel",
        int(split_buurt["buurtcode"].nunique())
        if len(split_buurt) else 0
    )

    if len(projects):
        totaal_projecten = pd.to_numeric(projects.get("aantal"), errors="coerce").sum()

        st.metric(
            "Geplande woningen (1.200-lijst)",
            int(totaal_projecten) if not pd.isna(totaal_projecten) else 0
        )

    # -------------------------
    # KAART
    # -------------------------
    with col_map:
        m = folium.Map(location=[52.299, 5.241], zoom_start=12)

        # BUURTEN HEATMAP
        if len(buurten):
            merged = buurten.merge(split_buurt, on="buurtcode", how="left")
            merged["expected_units_added"] = merged["expected_units_added"].fillna(0)

            if "buurtnaam" not in merged.columns:
                merged["buurtnaam"] = merged["buurtcode"]

            merged["potentieel_pct"] = (
                merged["expected_units_added"] * 100
            ).round(2)

            folium.Choropleth(
                geo_data=merged,
                data=merged,
                columns=["buurtcode", "expected_units_added"],
                key_on="feature.properties.buurtcode",
                fill_color="RdYlGn_r",
                fill_opacity=0.7,
                line_opacity=0.2,
                legend_name="Splitsingspotentieel",
            ).add_to(m)

            folium.GeoJson(
                merged,
                style_function=lambda x: {
                    "fillOpacity": 0,
                    "color": "black",
                    "weight": 0.5,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["buurtnaam", "potentieel_pct"],
                    aliases=["Buurt", "Potentieel (%)"],
                ),
            ).add_to(m)

        # WONINGEN
        if len(candidate_points):
            cluster = MarkerCluster().add_to(m)

            for _, r in candidate_points.iterrows():
                kans = r.get("p_le_2", 0)
                kans_pct = round(kans * 100, 1)

                kleur = (
                    "green" if kans > 0.7
                    else "orange" if kans > 0.5
                    else "red"
                )

                folium.CircleMarker(
                    location=[r.geometry.y, r.geometry.x],
                    radius=4,
                    color=kleur,
                    fill=True,
                    fill_opacity=0.7,
                    tooltip=f"""
                    <b>Woning</b><br>
                    Oppervlakte: {round(r.get('oppervlakte_m2', 0))} m²<br>
                    Kans ≤2 bewoners: {kans_pct}%
                    """,
                ).add_to(cluster)

        # PROJECTEN
        if len(projects):
            for _, r in projects.iterrows():
                folium.CircleMarker(
                    location=[r.geometry.y, r.geometry.x],
                    radius=6,
                    color="purple",
                    fill=True,
                    fill_opacity=0.9,
                    tooltip=f"""
                    <b>{r.get('benaming','')}</b><br>
                    {r.get('locatie','')}<br>
                    Woningen: {r.get('aantal','')}<br>
                    Status: {r.get('status','')}
                    """,
                ).add_to(m)

        st_folium(m, width=1100, height=650)

    # -------------------------
    # OVERLAP ANALYSE
    # -------------------------
    if len(projects) and len(buurten):
        st.subheader("Analyse: projecten vs splitsingspotentieel")

        try:
            projects_clean = clean_gdf_for_join(projects)
            buurten_clean = clean_gdf_for_join(buurten)

            projects_join = gpd.sjoin(
                projects_clean,
                buurten_clean[["buurtcode", "geometry"]],
                how="left",
                predicate="within"
            )

            projects_analysis = projects_join.merge(
                split_buurt,
                on="buurtcode",
                how="left"
            )

            st.dataframe(
                projects_analysis[
                    ["benaming", "buurtcode", "expected_units_added"]
                ].sort_values("expected_units_added", ascending=False)
            )

        except Exception as e:
            st.warning("Overlap analyse kon niet worden uitgevoerd.")
            st.write(e)

    # -------------------------
    # GRAFIEKEN
    # -------------------------
    col1, col2 = st.columns(2)

    with col1:
        if len(split_buurt):
            split_named = split_buurt.merge(
                buurten[["buurtcode", "buurtnaam"]],
                on="buurtcode",
                how="left"
            )

            fig = px.bar(
                split_named.sort_values("expected_units_added", ascending=False).head(10),
                x="buurtnaam",
                y="expected_units_added",
                title="Top buurten",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if len(candidates):
            fig = px.scatter(
                candidates,
                x="oppervlakte_m2",
                y="expected_units_added",
                title="Woninggrootte vs potentieel",
            )
            st.plotly_chart(fig, use_container_width=True)

    # DOWNLOAD
    if len(candidates):
        st.download_button(
            "Download dataset",
            data=candidates.to_csv(index=False).encode("utf-8"),
            file_name="split_candidates.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
