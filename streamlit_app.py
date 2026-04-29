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

def load_csv(name):
    path = PROCESSED / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_geo(name):
    path = PROCESSED / name
    if not path.exists():
        return gpd.GeoDataFrame()
    return gpd.read_file(path)


def clean_for_join(gdf):
    if len(gdf) == 0:
        return gdf
    gdf = gdf.copy()
    for col in ["index_left", "index_right"]:
        if col in gdf.columns:
            gdf = gdf.drop(columns=[col])
    return gdf


# -------------------------
# MAIN
# -------------------------

def main():
    st.title("Huizen Woningsplitsing Analyzer")

    st.markdown("""
    Deze tool laat zien waar binnen Huizen **bestaande woningen mogelijk beter benut kunnen worden**  
    en hoe dit zich verhoudt tot de geplande woningbouw.

    **Interpretatie:**
    - Grote woningen + kleine huishoudens → kans op splitsing
    - Buurten tonen het **totale potentieel in aantal woningen**
    - Punten tonen individuele woningen met indicatieve kans

    Ontwikkeld door [Ruben Woudsma](https://rubenwoudsma.nl)
    """)

    # DATA
    candidates = load_csv("split_candidates_public.csv")
    candidate_points = load_geo("split_candidates_public.geojson")
    split_buurt = load_csv("split_potential_buurt_public.csv")
    buurten = load_geo("buurten_huizen.geojson")
    projects = load_geo("wimra_1200_list.geojson")

    # FILTER
    col1, col2 = st.columns([1, 3])

    with col1:
        min_m2 = st.slider("Minimale woninggrootte (m²)", 80, 250, 120)
        adoptie = st.slider("Adoptie (%)", 1, 30, 10)

    if len(candidates):
        candidates = candidates[candidates["oppervlakte_m2"] >= min_m2]
        candidates["expected_units_added"] = (
            candidates["units_added_if_split"] *
            candidates["p_le_2"] *
            (adoptie / 100)
        )

    if len(candidate_points):
        candidate_points = candidate_points[
            candidate_points["oppervlakte_m2"] >= min_m2
        ]

    # KPI'S MET UITLEG
    st.subheader("Samenvatting")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Kandidaat-adressen",
        len(candidates),
        help="Aantal woningen groter dan de gekozen minimale oppervlakte"
    )

    c2.metric(
        "Verwachte extra woningen",
        round(candidates["expected_units_added"].sum(), 1),
        help="Indicatief aantal woningen bij gekozen adoptiepercentage"
    )

    c3.metric(
        "Buurten met potentieel",
        split_buurt["buurtcode"].nunique(),
        help="Aantal buurten waar splitsingspotentieel aanwezig is"
    )

    if len(projects):
        totaal = pd.to_numeric(projects["aantal"], errors="coerce").sum()
        c4.metric(
            "Geplande woningen",
            int(totaal),
            help="Aantal woningen uit de 1.200-lijst"
        )

    # -------------------------
    # KAART
    # -------------------------
    with col2:
        m = folium.Map(location=[52.299, 5.241], zoom_start=12)

        # BUURTEN
        if len(buurten):
            merged = buurten.merge(split_buurt, on="buurtcode", how="left")
            merged["expected_units_added"] = merged["expected_units_added"].fillna(0)

            if "buurtnaam" not in merged.columns:
                merged["buurtnaam"] = merged["buurtcode"]

            folium.Choropleth(
                geo_data=merged,
                data=merged,
                columns=["buurtcode", "expected_units_added"],
                key_on="feature.properties.buurtcode",
                fill_color="RdYlGn_r",
                legend_name="Aantal extra woningen",
            ).add_to(m)

            folium.GeoJson(
                merged,
                tooltip=folium.GeoJsonTooltip(
                    fields=["buurtnaam", "expected_units_added"],
                    aliases=["Buurt", "Extra woningen"],
                )
            ).add_to(m)

        # WONINGEN
        if len(candidate_points):
            cluster = MarkerCluster().add_to(m)

            for _, r in candidate_points.iterrows():
                kans = r.get("p_le_2", 0)

                kleur = (
                    "green" if kans > 0.7 else
                    "orange" if kans > 0.5 else
                    "red"
                )

                folium.CircleMarker(
                    location=[r.geometry.y, r.geometry.x],
                    radius=3,
                    color=kleur,
                    fill=True,
                    tooltip=f"""
                    Oppervlakte: {int(r['oppervlakte_m2'])} m²<br>
                    Kans: {round(kans*100,1)}%
                    """
                ).add_to(cluster)

        # PROJECTEN
        if len(projects):
            for _, r in projects.iterrows():
                folium.CircleMarker(
                    location=[r.geometry.y, r.geometry.x],
                    radius=6,
                    color="purple",
                    fill=True,
                    tooltip=f"{r.get('benaming','')} ({r.get('aantal','')})"
                ).add_to(m)

        st_folium(m, height=600)

    # -------------------------
    # OVERLAP ANALYSE
    # -------------------------
    st.subheader("Analyse projecten vs potentieel")

    if len(projects) and len(buurten):
        try:
            pj = gpd.sjoin(
                clean_for_join(projects),
                clean_for_join(buurten[["buurtcode", "geometry"]]),
                predicate="within"
            )

            analyse = pj.merge(split_buurt, on="buurtcode", how="left")
            analyse = analyse.merge(
                buurten[["buurtcode", "buurtnaam"]],
                on="buurtcode",
                how="left"
            )

            analyse = analyse.rename(columns={
                "expected_units_added": "Potentieel (woningen)",
                "buurtnaam": "Buurt"
            })

            st.dataframe(
                analyse[["benaming", "Buurt", "Potentieel (woningen)"]]
            )

        except Exception as e:
            st.warning("Analyse kon niet worden uitgevoerd")

    # -------------------------
    # GRAFIEKEN
    # -------------------------
    colA, colB = st.columns(2)

    with colA:
        if len(split_buurt):
            fig = px.bar(
                split_buurt.sort_values("expected_units_added", ascending=False).head(10),
                x="buurtcode",
                y="expected_units_added",
                title="Top buurten (aantal woningen)"
            )
            st.plotly_chart(fig, use_container_width=True)

    with colB:
        if len(candidates):
            fig = px.scatter(
                candidates,
                x="oppervlakte_m2",
                y="p_le_2",
                title="Woninggrootte vs kans op splitsing",
                opacity=0.4
            )
            st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
