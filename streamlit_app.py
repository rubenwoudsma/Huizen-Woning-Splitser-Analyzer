from pathlib import Path
import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import plotly.express as px

PROCESSED = Path("data/processed")


def load_csv(name):
    path = PROCESSED / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def load_geo(name):
    path = PROCESSED / name
    return gpd.read_file(path) if path.exists() else gpd.GeoDataFrame()


st.title("Huizen Woningsplitsing Analyzer")

st.markdown("""
Deze tool toont het splitsingspotentieel van bestaande woningen in Huizen
en vergelijkt dit met geplande bouwprojecten.
""")

candidates = load_csv("split_candidates_public.csv")
candidate_points = load_geo("split_candidates_public.geojson")
split_buurt = load_csv("split_potential_buurt_public.csv")
buurten = load_geo("buurten_huizen.geojson")
projects = load_geo("wimra_1200_list.geojson")

min_m2 = st.slider("Min woninggrootte", 80, 250, 120)

candidates = candidates[candidates["oppervlakte_m2"] >= min_m2]

st.metric("Kandidaat-adressen", len(candidates))
st.metric("Extra woningen", round(candidates["expected_units_added"].sum()))

m = folium.Map(location=[52.3, 5.24], zoom_start=12)

merged = buurten.merge(split_buurt, on="buurtcode", how="left")
merged["expected_units_added"] = merged["expected_units_added"].fillna(0).round(0)

folium.Choropleth(
    geo_data=merged,
    data=merged,
    columns=["buurtcode", "expected_units_added"],
    key_on="feature.properties.buurtcode",
).add_to(m)

cluster = MarkerCluster().add_to(m)

for _, r in candidate_points.iterrows():
    folium.CircleMarker(
        [r.geometry.y, r.geometry.x],
        radius=3,
        color="blue",
        tooltip=f"{int(r['oppervlakte_m2'])} m²"
    ).add_to(cluster)

for _, r in projects.iterrows():
    folium.CircleMarker(
        [r.geometry.y, r.geometry.x],
        radius=6,
        color="purple",
        tooltip=r.get("benaming", "")
    ).add_to(m)

st_folium(m, height=700)

if len(candidates):
    fig = px.scatter(
        candidates[candidates["oppervlakte_m2"] < 500],
        x="oppervlakte_m2",
        y="p_le_2"
    )
    st.plotly_chart(fig)
