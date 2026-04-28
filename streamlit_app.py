from __future__ import annotations

from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

PROCESSED = Path("data/processed")

st.set_page_config(page_title="Huizen Woningsplitsing Analyzer", layout="wide")


# -------------------------
# DATA LOADERS
# -------------------------

@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_data
def load_geojson(name: str):
    path = PROCESSED / name
    if not path.exists():
        return gpd.GeoDataFrame()
    try:
        return gpd.read_file(path)
    except Exception:
        return gpd.GeoDataFrame()


# -------------------------
# MAIN
# -------------------------

def main():
    st.title("Huizen Woningsplitsing Analyzer")

    # DATA
    candidates = load_csv("split_candidates_public.csv")
    candidate_points = load_geojson("split_candidates_public.geojson")
    split_buurt = load_csv("split_potential_buurt_public.csv")
    buurten = load_geojson("buurten_huizen.geojson")

    # FILTERS
    col_filter, col_map = st.columns([1, 3])

    with col_filter:
        min_m2 = st.slider("Minimale oppervlakte", 80, 250, 120, 5)

    if len(candidates):
        candidates = candidates[candidates["oppervlakte_m2"] >= min_m2]

    # KPI'S
    k1, k2, k3 = st.columns(3)

    k1.metric(
        "Kandidaat-adressen",
        int(candidates["adres_id"].nunique()) if len(candidates) else 0
    )

    k2.metric(
        "Verwachte extra woningen",
        round(float(candidates["expected_units_added"].sum()), 1) if len(candidates) else 0
    )

    k3.metric(
        "Buurten met potentieel",
        int(split_buurt["buurtcode"].nunique()) if len(split_buurt) else 0
    )

    # -------------------------
    # KAART
    # -------------------------

    with col_map:
        m = folium.Map(location=[52.299, 5.241], zoom_start=12, tiles="cartodbpositron")

        # KOPPEL BUURTEN AAN DATA
        if len(buurten) and len(split_buurt):
            merged = buurten.merge(split_buurt, on="buurtcode", how="left")
            merged["expected_units_added"] = merged["expected_units_added"].fillna(0)

            # CHOROPLETH (belangrijk!)
            folium.Choropleth(
                geo_data=merged,
                data=merged,
                columns=["buurtcode", "expected_units_added"],
                key_on="feature.properties.buurtcode",
                fill_color="YlOrRd",
                fill_opacity=0.7,
                line_opacity=0.3,
                legend_name="Splitsingspotentieel",
            ).add_to(m)

            # TOOLTIP + RANDEN
            folium.GeoJson(
                merged,
                style_function=lambda x: {
                    "fillOpacity": 0,
                    "color": "black",
                    "weight": 0.5,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["buurtcode", "expected_units_added"],
                    aliases=["Buurt", "Potentieel"],
                ),
            ).add_to(m)

        # WONINGEN (punten)
        if len(candidate_points):
            for _, r in candidate_points.iterrows():
                folium.CircleMarker(
                    location=[r.geometry.y, r.geometry.x],
                    radius=3,
                    color="blue",
                    fill=True,
                    fill_opacity=0.6,
                    tooltip=f"""
                    Oppervlakte: {round(r.get('oppervlakte_m2', 0))} m²
                    Kans: {round(r.get('p_le_2', 0), 2)}
                    """,
                ).add_to(m)

        folium.LayerControl().add_to(m)
        st_folium(m, width=1100, height=650)

    # -------------------------
    # GRAFIEKEN
    # -------------------------

    c1, c2 = st.columns(2)

    with c1:
        if len(split_buurt):
            fig = px.bar(
                split_buurt.sort_values("expected_units_added", ascending=False).head(10),
                x="buurtcode",
                y="expected_units_added",
                title="Top buurten (splitsingspotentieel)",
            )
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if len(candidates):
            fig = px.histogram(
                candidates,
                x="oppervlakte_m2",
                nbins=20,
                title="Verdeling woningoppervlak",
            )
            st.plotly_chart(fig, use_container_width=True)

    # DOWNLOAD
    if len(candidates):
        st.download_button(
            "Download data",
            data=candidates.to_csv(index=False).encode("utf-8"),
            file_name="split_candidates.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
