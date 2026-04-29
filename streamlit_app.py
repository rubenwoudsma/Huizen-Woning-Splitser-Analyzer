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
@st.cache_data
def load_csv(name):
    path = PROCESSED / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_data
def load_geo(name):
    path = PROCESSED / name
    return gpd.read_file(path) if path.exists() else gpd.GeoDataFrame()


@st.cache_data
def calculate_candidates(df, min_m2, adoptie):
    if len(df) == 0:
        return df
    df = df[df["oppervlakte_m2"] >= min_m2].copy()
    df["expected_units_added"] = (
        df["units_added_if_split"] * df["p_le_2"] * (adoptie / 100)
    )
    return df


# -------------------------
# HEADER
# -------------------------
st.title("Huizen Woningsplitsing Analyzer")

st.markdown("""
Deze tool laat zien waar binnen Huizen **bestaande woningen beter benut kunnen worden**  
en hoe dit zich verhoudt tot geplande woningbouw.

**Hoe lees je de kaart?**

- 🔴 Buurten: totaal potentieel voor extra woningen  
- 🔵 Woningen: kans dat splitsing mogelijk is  
- 🟣 Projecten: geplande woningbouw  

👉 Hoe hoger de kans bij een woning, hoe groter de kans dat deze geschikt is voor splitsing.
""")

# -------------------------
# DATA
# -------------------------
candidates_raw = load_csv("split_candidates_public.csv")
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

candidates = calculate_candidates(candidates_raw, min_m2, adoptie)

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
# KAART
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
        legend_name="Extra woningen",
    ).add_to(m)

    folium.GeoJson(
        merged,
        style_function=lambda x: {"fillOpacity": 0, "color": "black", "weight": 0.5},
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
            "green" if kans > 0.7 else
            "orange" if kans > 0.5 else
            "red"
        )

        folium.CircleMarker(
            [r.geometry.y, r.geometry.x],
            radius=3,
            color=kleur,
            fill=True,
            tooltip=f"""
            Woning<br>
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
            {r.get('benaming','')}<br>
            {r.get('locatie','')}<br>
            Aantal woningen: {r.get('aantal','')}<br>
            Status: {r.get('status','')}
            """
        ).add_to(m)

st_folium(m, use_container_width=True, height=750, returned_objects=[])

st.caption("Let op: bij in- en uitzoomen kan de kaart kort verversen.")

# -------------------------
# ANALYSE
# -------------------------
st.subheader("Analyse: projecten vs splitsingspotentieel")

if len(projects) and len(split_buurt):

    analyse = projects.merge(split_buurt, on="buurtcode", how="left")

    analyse["Projectgrootte"] = pd.to_numeric(analyse["aantal"], errors="coerce")
    analyse["Potentieel (woningen)"] = analyse["expected_units_added"].fillna(0)

    analyse["Verhouding"] = (
        analyse["Projectgrootte"] /
        analyse["Potentieel (woningen)"]
    )

    def categoriseer(row):
        if pd.isna(row["Verhouding"]):
            return "⚪ Onbekend"
        elif row["Verhouding"] > 1:
            return "🔴 Overbelast"
        elif row["Verhouding"] < 0.5:
            return "🟢 Onderbenut"
        else:
            return "🟡 In balans"

    analyse["Categorie"] = analyse.apply(categoriseer, axis=1)

    analyse["Potentieel (woningen)"] = analyse["Potentieel (woningen)"].round(0).astype(int)
    analyse["Verhouding"] = analyse["Verhouding"].round(2)

    st.dataframe(
        analyse[
            ["benaming", "buurtnaam", "Projectgrootte", "Potentieel (woningen)", "Verhouding", "Categorie"]
        ].rename(columns={"buurtnaam": "Buurt"})
    )

# -------------------------
# GRAFIEKEN
# -------------------------
colA, colB = st.columns(2)

with colA:
    if len(split_buurt) and len(projects):

        # projecten optellen per buurt
        projecten_per_buurt = projects.groupby("buurtcode")["aantal"].apply(
            lambda x: pd.to_numeric(x, errors="coerce").sum()
        ).reset_index()

        vergelijking = split_buurt.merge(
            projecten_per_buurt,
            on="buurtcode",
            how="left"
        )

        vergelijking["aantal"] = vergelijking["aantal"].fillna(0)

        vergelijking = vergelijking.merge(
            buurten[["buurtcode", "buurtnaam"]],
            on="buurtcode",
            how="left"
        )

        # 🔥 HERNOEMEN (BELANGRIJK)
        vergelijking = vergelijking.rename(columns={
            "expected_units_added": "Potentieel (woningen)",
            "aantal": "Geplande woningen"
        })

        # 🔥 AFRONDEN
        vergelijking["Potentieel (woningen)"] = (
            vergelijking["Potentieel (woningen)"].round(0).astype(int)
        )

        vergelijking["Geplande woningen"] = (
            pd.to_numeric(vergelijking["Geplande woningen"], errors="coerce")
            .fillna(0)
            .round(0)
            .astype(int)
        )

        # 🔥 GRAFIEK
        fig = px.bar(
            vergelijking.sort_values("Potentieel (woningen)", ascending=False).head(10),
            x="buurtnaam",
            y=["Potentieel (woningen)", "Geplande woningen"],
            barmode="group",
            title="Potentieel vs geplande woningen per buurt",
            labels={
                "value": "Aantal woningen",
                "variable": "Type"
            }
        )

        # 🔥 KLEUREN TOEVOEGEN
        fig.update_traces(
            selector=dict(name="Potentieel (woningen)"),
            marker_color="#2ca02c"
        )

        fig.update_traces(
            selector=dict(name="Geplande woningen"),
            marker_color="#d62728"
        )

        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "Groen = potentieel via splitsing, rood = geplande woningbouw."
        )

with colB:
        fig = px.pie(
            analyse,
            names="Categorie",
            title="Verdeling projecten over categorieën",
            color="Categorie",
            color_discrete_map={
                "🔴 Overbelast": "#ff4d4d",
                "🟢 Onderbenut": "#4dff88",
                "🟡 In balans": "#ffd24d"
            }
        )
        
        st.plotly_chart(fig)
