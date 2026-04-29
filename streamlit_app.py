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


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(path)
        return safe_lower(df)
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_geojson(name: str):
    path = PROCESSED / name
    if not path.exists():
        return gpd.GeoDataFrame()

    try:
        gdf = gpd.read_file(path)
        return safe_lower(gdf)
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
        Deze tool geeft inzicht in het **potentieel voor woningsplitsing in de gemeente Huizen**.  
        Het doel is om beter te begrijpen waar binnen bestaande wijken extra woonruimte kan ontstaan.

        Ontwikkeld door [Ruben Woudsma](https://rubenwoudsma.nl)
        """
    )

    st.info(
        "Dit model is indicatief. De resultaten geven richting voor beleid en analyse, "
        "maar zijn geen exacte voorspellingen."
    )

    # DATA
    candidates = load_csv("split_candidates_public.csv")
    candidate_points = load_geojson("split_candidates_public.geojson")
    split_buurt = load_csv("split_potential_buurt_public.csv")
    buurten = load_geojson("buurten_huizen.geojson")

    buurten = ensure_buurtcode(buurten)
    split_buurt = ensure_buurtcode(split_buurt)

    # FILTER
    col_filter, col_map = st.columns([1, 3])

    with col_filter:
        min_m2 = st.slider("Minimale woninggrootte (m²)", 80, 250, 120, 5)

    if len(candidates):
        candidates = candidates[candidates["oppervlakte_m2"] >= min_m2]

    if len(candidate_points):
        candidate_points = candidate_points[
            candidate_points["oppervlakte_m2"] >= min_m2
        ]

    # KPI'S
    k1, k2, k3 = st.columns(3)

    k1.metric("Kandidaat-adressen", int(len(candidates)))

    k2.metric(
        "Verwachte extra woningen",
        round(float(candidates.get("expected_units_added", pd.Series([0])).sum()), 1)
    )

    k3.metric(
        "Buurten met potentieel",
        int(split_buurt["buurtcode"].nunique())
        if "buurtcode" in split_buurt.columns else 0
    )

    # -------------------------
    # KAART
    # -------------------------
    with col_map:
        m = folium.Map(location=[52.299, 5.241], zoom_start=12, tiles="cartodbpositron")

        if len(buurten):
            if len(split_buurt):
                merged = buurten.merge(split_buurt, on="buurtcode", how="left")
            else:
                merged = buurten.copy()

            merged["expected_units_added"] = merged.get("expected_units_added", 0)
            merged["expected_units_added"] = merged["expected_units_added"].fillna(0)

            # buurtnamen fix
            if "buurtnaam" not in merged.columns:
                merged["buurtnaam"] = merged["buurtcode"]

            # percentage toevoegen
            merged["potentieel_pct"] = (merged["expected_units_added"] * 100).round(2)

            # heatmap
            min_val = merged["expected_units_added"].min()
            max_val = merged["expected_units_added"].max()

            if max_val > min_val:
                thresholds = [
                    min_val,
                    min_val + (max_val - min_val) * 0.25,
                    min_val + (max_val - min_val) * 0.5,
                    min_val + (max_val - min_val) * 0.75,
                    max_val,
                ]
            else:
                thresholds = [0, 1]

            folium.Choropleth(
                geo_data=merged,
                data=merged,
                columns=["buurtcode", "expected_units_added"],
                key_on="feature.properties.buurtcode",
                fill_color="RdYlGn_r",
                fill_opacity=0.8,
                line_opacity=0.2,
                threshold_scale=thresholds,
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

        # woningen (punten)
        if len(candidate_points):
            cluster = MarkerCluster().add_to(m)

            for _, r in candidate_points.iterrows():
                kans = r.get("p_le_2", 0)
                kans_pct = round(kans * 100, 1)

                if kans > 0.7:
                    kleur = "green"
                elif kans > 0.5:
                    kleur = "orange"
                else:
                    kleur = "red"

                tooltip = folium.Tooltip(
                    f"""
                    <b>Woning</b><br>
                    Oppervlakte: {round(r.get('oppervlakte_m2', 0))} m²<br>
                    Kans op kleine huishoudens (≤2 pers): {kans_pct}%<br>
                    <br>
                    <i>Hoe hoger deze kans, hoe groter de kans dat deze woning geschikt is voor splitsing</i>
                    """,
                    sticky=True,
                )

                folium.CircleMarker(
                    location=[r.geometry.y, r.geometry.x],
                    radius=4,
                    color=kleur,
                    fill=True,
                    fill_opacity=0.7,
                    tooltip=tooltip,
                ).add_to(cluster)

        folium.LayerControl().add_to(m)
        st_folium(m, width=1100, height=650)

    # -------------------------
    # GRAFIEKEN
    # -------------------------
    c1, c2 = st.columns(2)

    with c1:
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
                title="Top buurten (splitsingspotentieel)",
            )
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if len(candidates):
            fig = px.scatter(
                candidates,
                x="oppervlakte_m2",
                y="expected_units_added",
                title="Relatie woninggrootte vs splitsingspotentieel",
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
