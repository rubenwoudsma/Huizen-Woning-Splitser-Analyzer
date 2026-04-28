from __future__ import annotations

from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium


PROCESSED = Path("data/processed")
KEA_WMS = "https://apps.geodan.nl/public/data/org/gws/YWFMLMWERURF/kea_public/wms"


st.set_page_config(page_title="Huizen Woningsplitsing Analyzer", layout="wide")


def auth_gate() -> None:
    expected = st.secrets.get("APP_PASSWORD")
    if not expected:
        return
    if st.session_state.get("ok"):
        return
    pwd = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if pwd == expected:
            st.session_state["ok"] = True
            st.rerun()
        st.error("Onjuist wachtwoord.")
    st.stop()


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_data
def load_geojson(name: str):
    path = PROCESSED / name
    if not path.exists():
        st.warning(f"{name} ontbreekt")
        return gpd.GeoDataFrame()
    try:
        return gpd.read_file(path)
    except Exception as e:
        st.error(f"Fout bij laden {name}: {e}")
        return gpd.GeoDataFrame()

st.write("Files in data/processed:", list(PROCESSED.glob("*")))

def main() -> None:
    auth_gate()
    st.title("Huizen Woningsplitsing Analyzer")

    candidates = load_csv("split_candidates_public.csv")
    candidate_points = load_geojson("split_candidates_public.geojson")
    split_buurt = load_csv("split_potential_buurt_public.csv")
    buurten = load_geojson("buurten_huizen.geojson")
    projects = load_geojson("wimra_1200_list_geocoded.geojson")
    realisatie = load_csv("wimra_realisatiegraad_summary.csv")


    left, right = st.columns([1, 3])

    with left:
        min_m2 = st.slider("Minimale oppervlakte", 80, 250, 120, 5)
        show_heat = st.checkbox("Toon hittestress-WMS", value=True)
        status_filter = ["alle"]
        if "status_bucket" in projects.columns and len(projects):
            status_filter += sorted(projects["status_bucket"].dropna().unique().tolist())
        chosen_status = st.selectbox("Projectstatus", status_filter)

    if len(candidates):
        candidates = candidates[candidates["oppervlakte_m2"] >= min_m2].copy()

    k1, k2, k3 = st.columns(3)
    k1.metric("Kandidaat-adressen", int(candidates["adres_id"].nunique()) if len(candidates) else 0)
    k2.metric("Verwachte extra woningen", round(float(candidates["expected_units_added"].sum()), 1) if len(candidates) else 0.0)
    k3.metric("Buurten met potentieel", int(split_buurt["buurtcode"].nunique()) if len(split_buurt) else 0)

    with right:
        m = folium.Map(location=[52.299, 5.241], zoom_start=12, tiles="cartodbpositron")
        if len(buurten):
            merged = buurten.merge(split_buurt, on="buurtcode", how="left")
            folium.GeoJson(
                merged.to_json(),
                tooltip=folium.GeoJsonTooltip(fields=["buurtnaam", "expected_units_added"]),
                name="Split potentieel per buurt",
            ).add_to(m)

        if len(projects):
            p = projects.copy()
            if chosen_status != "alle":
                p = p[p["status_bucket"] == chosen_status].copy()
            for _, r in p.dropna(subset=["geometry"]).iterrows():
                folium.CircleMarker(
                    location=[r.geometry.y, r.geometry.x],
                    radius=4,
                    tooltip=f"{r.get('benaming', 'project')} | {r.get('status_bucket', '')}",
                ).add_to(m)

        if len(candidate_points):
            for _, r in candidate_points.dropna(subset=["geometry"]).head(2000).iterrows():
                folium.CircleMarker(
                    location=[r.geometry.y, r.geometry.x],
                    radius=2,
                    tooltip=f"{r.get('oppervlakte_m2', '')} m2 | p<=2: {round(r.get('p_le_2', 0), 2)}",
                    fill=True,
        ).add_to(m)

        folium.LayerControl().add_to(m)
        st_folium(m, width=1100, height=650)

    c1, c2 = st.columns(2)

    with c1:
        if len(split_buurt):
            fig = px.bar(
                split_buurt.sort_values("expected_units_added", ascending=False).head(15),
                x="buurtcode",
                y="expected_units_added",
                title="Top buurten naar verwacht splitsingspotentieel",
            )
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if len(realisatie):
            fig = px.bar(
                realisatie,
                x="status_bucket",
                y="woningaantal",
                title="1.200-lijst naar statusklasse",
            )
            st.plotly_chart(fig, use_container_width=True)

    if len(candidates):
        st.download_button(
            "Download kandidaat-adressen als CSV",
            data=candidates.to_csv(index=False).encode("utf-8"),
            file_name="split_candidates_public.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
