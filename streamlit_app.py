from pathlib import Path
import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import plotly.express as px

PROCESSED = Path("data/processed")

st.set_page_config(page_title="Huizen Woningsplitsing Analyzer", layout="wide")


# -------------------------
# DATA LOADERS
# -------------------------
def load_csv(name):
    path = PROCESSED / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def load_geo(name):
    path = PROCESSED / name
    return gpd.read_file(path) if path.exists() else gpd.GeoDataFrame()


def clean_for_join(gdf):
    gdf = gdf.copy()
    for col in ["index_left", "index_right"]:
        if col in gdf.columns:
            gdf = gdf.drop(columns=[col])
    return gdf


# -------------------------
# APP START
# -------------------------

st.title("Huizen Woningsplitsing Analyzer")

st.markdown("""
Deze tool geeft inzicht in het **potentieel voor woningsplitsing binnen de bestaande woningvoorraad**  
en zet dit af tegen geplande woningbouw in Huizen.

### Wat zie je op de kaart?
- 🔴 Buurten → totaal potentieel (extra woningen)
- 🔵 Punten → individuele woningen met kans op splitsing
- 🟣 Paarse punten → geplande bouwprojecten

Ontwikkeld door [Ruben Woudsma](https://rubenwoudsma.nl)

Dit model is indicatief en bedoeld om inzicht te geven in potentieel, niet om exacte aantallen te voorspellen.
""")

# -------------------------
# DATA
# -------------------------
candidates = load_csv("split_candidates_public.csv")
candidate_points = load_geo("split_candidates_public.geojson")
split_buurt = load_csv("split_potential_buurt_public.csv")
buurten = load_geo("buurten_huizen.geojson")
projects = load_geo("wimra_1200_list.geojson")

# -------------------------
# FILTERS
# -------------------------
col1, col2 = st.columns(2)

with col1:
    min_m2 = st.slider("Minimale woninggrootte (m²)", 80, 250, 120)

with col2:
    adoptie = st.slider("Adoptie splitsing (%)", 1, 30, 10)

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
st.subheader("Samenvatting")

k1, k2, k3, k4 = st.columns(4)

k1.metric("Kandidaat-adressen", len(candidates))
k2.metric("Extra woningen", int(round(candidates["expected_units_added"].sum())))
k3.metric("Buurten met potentieel", split_buurt["buurtcode"].nunique())

if len(projects):
    totaal = pd.to_numeric(projects["aantal"], errors="coerce").sum()
    k4.metric("Geplande woningen", int(totaal))

# -------------------------
# KAART (FULL WIDTH)
# -------------------------
st.subheader("Kaart")

m = folium.Map(location=[52.3, 5.24], zoom_start=12)

# BUURTEN
if len(buurten):
    merged = buurten.merge(split_buurt, on="buurtcode", how="left")
    merged["expected_units_added"] = merged["expected_units_added"].fillna(0).round(0)

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
        style_function=lambda x: {
            "fillOpacity": 0,
            "color": "black",
            "weight": 0.5,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["buurtnaam", "expected_units_added"],
            aliases=["Buurt", "Extra woningen"],
        ),
    ).add_to(m)

# WONINGEN
if len(candidate_points):
    cluster = MarkerCluster().add_to(m)

    for _, r in candidate_points.iterrows():
        kans = r.get("p_le_2", 0)

        kleur = (
            "green" if kans > 0.7
            else "orange" if kans > 0.5
            else "red"
        )

        folium.CircleMarker(
            [r.geometry.y, r.geometry.x],
            radius=3,
            color=kleur,
            fill=True,
            tooltip=f"""
            Oppervlakte: {int(r['oppervlakte_m2'])} m²<br>
            Kans splitsing: {round(kans*100,1)}%
            """
        ).add_to(cluster)

# PROJECTEN
if len(projects):
    for _, r in projects.iterrows():
        folium.CircleMarker(
            [r.geometry.y, r.geometry.x],
            radius=6,
            color="purple",
            fill=True,
            tooltip=f"""
            <b>{r.get('benaming','')}</b><br>
            {r.get('locatie','')}<br>
            Woningen: {r.get('aantal','')}<br>
            Status: {r.get('status','')}
            """
        ).add_to(m)

st_folium(m, use_container_width=True, height=750)

st.caption(
    "Let op: bij in- en uitzoomen kan de kaart kort verversen. Even geduld als je de overlay ziet helpt."
)

# -------------------------
# OVERLAP ANALYSE
# -------------------------
st.subheader("Analyse: projecten vs splitsingspotentieel")

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
            "buurtnaam": "Buurt",
            "expected_units_added": "Potentieel (woningen)"
        })

        analyse = analyse.fillna({"Potentieel (woningen)": 0})

        st.dataframe(
            analyse[["benaming", "Buurt", "Potentieel (woningen)"]]
        )

    except Exception as e:
        st.warning("Analyse kon niet worden uitgevoerd")
        st.write(e)

# -------------------------
# GRAFIEKEN
# -------------------------
colA, colB = st.columns(2)

with colA:
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
            title="Top buurten"
        )
        st.plotly_chart(fig, use_container_width=True)

with colB:
    if len(candidates):
        filtered = candidates[candidates["oppervlakte_m2"] < 500]

        fig = px.scatter(
            filtered,
            x="oppervlakte_m2",
            y="p_le_2",
            opacity=0.4,
            title="Woninggrootte vs kans op splitsing"
        )
        st.plotly_chart(fig, use_container_width=True)
