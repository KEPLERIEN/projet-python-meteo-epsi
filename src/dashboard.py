import datetime
import logging
from io import BytesIO
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from .api_client import WeatherAPIClient, fetch_rainviewer_radar
    from .data_processing import DataProcessor
    from .alerts import detect_alerts
except ImportError:
    from api_client import WeatherAPIClient, fetch_rainviewer_radar
    from data_processing import DataProcessor
    from alerts import detect_alerts

# Configuration des logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DEFAULT_CITIES = {
    "Paris": {"lat": 48.8566, "lon": 2.3522},
    "Lyon": {"lat": 45.7640, "lon": 4.8357},
    "Marseille": {"lat": 43.2965, "lon": 5.3698},
    "Rennes": {"lat": 48.1113, "lon": -1.6800},
    "Grenoble": {"lat": 45.1885, "lon": 5.7245}
}

def build_pdf_report(city: str, latest: pd.Series, alerts: List[Dict[str, str]]) -> bytes:
    #Génère un rapport PDF des dernières mesures.
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Rapport météo et qualité de l'air", styles["Title"]),
        Spacer(1, 5 * mm),
        Paragraph(f"Ville : {escape(city)}", styles["Heading2"]),
        Paragraph(
            f"Dernière mesure : {escape(str(latest.get('datetime', 'Indisponible')))}",
            styles["Normal"],
        ),
        Spacer(1, 5 * mm),
    ]

    measurements = [
        ("temperature_2m", "Température", "°C"),
        ("relativehumidity_2m", "Humidité", "%"),
        ("us_aqi", "Indice AQI (US)", ""),
        ("pm2_5", "PM2.5", "µg/m³"),
        ("pm10", "PM10", "µg/m³"),
        ("nitrogen_dioxide", "Dioxyde d'azote (NO2)", "µg/m³"),
        ("ozone", "Ozone (O3)", "µg/m³"),
        ("sulphur_dioxide", "Dioxyde de soufre (SO2)", "µg/m³"),
        ("carbon_monoxide", "Monoxyde de carbone (CO)", "µg/m³"),
        ("surface_pressure", "Pression atmosphérique", "hPa"),
        ("windspeed_10m", "Vitesse du vent", "km/h"),
        ("health_score", "Score confort/santé", "/ 100"),
    ]
    rows = [["Indicateur", "Valeur"]]
    for key, label, unit in measurements:
        if key not in latest:
            continue
        value = latest[key]
        formatted_value = "Indisponible" if pd.isna(value) else f"{value:.1f} {unit}".strip()
        rows.append([label, formatted_value])

    table = Table(rows, colWidths=[100 * mm, 60 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#24476b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 7 * mm), Paragraph("Alertes", styles["Heading2"])])
    if alerts:
        story.extend(
            Paragraph(f"- {escape(alert['message'])}", styles["Normal"])
            for alert in alerts
        )
    else:
        story.append(Paragraph("Aucune alerte active.", styles["Normal"]))

    document.build(story)
    return output.getvalue()

def build_csv_export(data: pd.DataFrame) -> bytes:
    #Export des données au format CSV (UTF-8).
    return data.to_csv(index=False).encode("utf-8-sig")

# Paramètres radar RainViewer
RAINVIEWER_TILE_COLOR = 6  # Palette de couleurs
RAINVIEWER_TILE_OPTIONS = "1_1" # Options de rendu (lissage, neige)
RAINVIEWER_TILE_SIZE = 256 # Taille tuile
RAINVIEWER_OPACITY = 0.7 # Opacité
RAINVIEWER_ZOOM = 6 # Zoom initial
RAINVIEWER_FRAME_MS = 600 # Durée frame (ms)
RAINVIEWER_TRANSITION_MS = 250 # Transition (ms)

def build_radar_tile_url(host: str, frame_path: str) -> str:
    #Génère l'URL des tuiles radar pour Plotly.
    return (
        f"{host.rstrip('/')}{frame_path}/{RAINVIEWER_TILE_SIZE}"
        f"/{{z}}/{{x}}/{{y}}/{RAINVIEWER_TILE_COLOR}/{RAINVIEWER_TILE_OPTIONS}.png"
    )

def build_radar_layer(source: str) -> Dict[str, Any]:
    #Description du calque raster pour Plotly Mapbox.
    return {
        "sourcetype": "raster",
        "source": [source],
        "sourceattribution": "Radar : RainViewer",
        "opacity": RAINVIEWER_OPACITY,
    }

def build_radar_map(city: str, lat: float, lon: float, host: str, frames: List[Dict[str, str]], height: int = 700) -> go.Figure:
    #Carte Plotly animée avec calques radar RainViewer.
    labels = [frame["label"] for frame in frames]
    frame_names = [f"radar-{index}" for index in range(len(frames))]
    tile_urls = [build_radar_tile_url(host, frame["path"]) for frame in frames]

    station = pd.DataFrame([{"lat": lat, "lon": lon, "ville": city}])
    figure = px.scatter_mapbox(station, lat="lat", lon="lon", hover_name="ville", zoom=RAINVIEWER_ZOOM, height=height)
    figure.update_traces(marker=dict(size=14, color="#d81b60"))
    figure.update_layout(
        mapbox_style="open-street-map",
        mapbox_layers=[build_radar_layer(tile_urls[-1])], # Frame initiale (la plus récente)
        margin=dict(l=0, r=0, t=10, b=0),
        updatemenus=[{
            "type": "buttons",
            "direction": "left",
            "showactive": False,
            "buttons": [
                {
                    "label": "▶ Lecture",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": RAINVIEWER_FRAME_MS, "redraw": True}, "transition": {"duration": RAINVIEWER_TRANSITION_MS}, "fromcurrent": False, "mode": "immediate"}]
                },
                {
                    "label": "⏸ Pause",
                    "method": "animate",
                    "args": [[None], {"frame": {"duration": 0, "redraw": False}, "transition": {"duration": 0}, "mode": "immediate"}]
                }
            ]
        }],
        sliders=[{
            "active": len(frames) - 1,
            "currentvalue": {"prefix": "Échéance : "},
            "steps": [
                {
                    "label": label,
                    "method": "animate",
                    "args": [[name], {"frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}, "mode": "immediate"}]
                }
                for label, name in zip(labels, frame_names)
            ]
        }]
    )

    figure.frames = [
        go.Frame(name=name, layout=go.Layout(mapbox=go.layout.Mapbox(layers=[build_radar_layer(url)])))
        for name, url in zip(frame_names, tile_urls)
    ]
    return figure

def build_radar_frames(radar: Dict[str, Any]) -> List[Dict[str, str]]:
    #Prépare les frames radar (passé + prévision).
    frames: List[Dict[str, str]] = []
    radar_data = radar.get("radar", {})
    for entry in radar_data.get("past", []):
        frames.append({
            "path": entry["path"],
            "label": datetime.datetime.fromtimestamp(entry["time"]).strftime("%H:%M"),
        })
    for entry in radar_data.get("nowcast", []):
        frames.append({
            "path": entry["path"],
            "label": datetime.datetime.fromtimestamp(entry["time"]).strftime("%H:%M (prévu)"),
        })
    return frames

@st.cache_data(ttl=300)
def load_rainviewer_radar() -> Optional[Dict[str, Any]]:
    #Récupère les métadonnées radar (cache 5 min).
    return fetch_rainviewer_radar()

def render_dashboard():
    #Interface de l'application Streamlit.
    st.set_page_config(page_title="Dashboard Météo & AQI", page_icon="🌤️", layout="wide")

    st.title("🌤️ Dashboard Météo & Surveillance Qualité de l'Air")
    st.markdown("Projet 3ᵉ Année Ingénieur — Analyse de données environnementales en temps réel")

    client = WeatherAPIClient()

    # Configuration latérale
    st.sidebar.header("⚙️ Configuration")
    selected_city = st.sidebar.selectbox("Sélectionner une ville", list(DEFAULT_CITIES.keys()))
    mock_mode = st.sidebar.checkbox("Mode Déconnecté / Data Mocked", value=False)

    city_info = DEFAULT_CITIES[selected_city]

    # Chargement des données
    with st.spinner(f"Chargement des données pour {selected_city}..."):
        if mock_mode:
            mock_data_key = f"mock_weather_data_{selected_city}"
            if mock_data_key not in st.session_state:
                st.session_state[mock_data_key] = client.fetch_weather_and_air_quality(
                    city_info["lat"],
                    city_info["lon"],
                    mock_mode=True,
                )
            raw_data = st.session_state[mock_data_key]
        else:
            raw_data = client.fetch_weather_and_air_quality(
                city_info["lat"],
                city_info["lon"],
            )
        df = DataProcessor.process_raw_api_data(raw_data)

    if df.empty:
        st.error("Impossible de récupérer ou d'afficher les données.")
        return

    # Calcul des métriques
    df["health_score"] = DataProcessor.calculate_custom_health_index(df)
    current_weather = raw_data.get("weather", {}).get("current_weather", {})
    current_data = DataProcessor.select_current_observation(
        df,
        current_weather.get("time"),
    )
    latest = current_data.iloc[-1].copy()
    current_temperature = pd.to_numeric(
        pd.Series([current_weather.get("temperature")]),
        errors="coerce",
    ).iloc[0]
    if pd.notna(current_temperature):
        latest["temperature_2m"] = current_temperature
        latest["health_score"] = DataProcessor.calculate_custom_health_index(
            pd.DataFrame([latest])
        ).iloc[0]

    aqi_values = pd.to_numeric(current_data["us_aqi"], errors="coerce").dropna()
    latest_aqi = aqi_values.iloc[-1] if not aqi_values.empty else None

    # Alertes
    alerts = detect_alerts(pd.DataFrame([latest]))
    if alerts:
        for alert in alerts:
            if alert["level"] == "danger":
                st.error(f"🚨 **DANGER** : {alert['message']}")
            else:
                st.warning(f"⚠️ **ATTENTION** : {alert['message']}")
    else:
        st.success("✅ Conditions stables. Aucune alerte active.")

    # Cartes KPI
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Température", f"{latest['temperature_2m']:.1f} °C")
    col2.metric("Humidité", f"{latest['relativehumidity_2m']:.0f} %")
    col3.metric("Indice AQI (US)", latest_aqi)
    col4.metric("PM 2.5", f"{latest['pm2_5']:.1f} µg/m³")
    col5.metric("Score Confort (0-100)", f"{latest['health_score']:.1f}")

    # Téléchargements des données CSV et PDF
    csv_data = build_csv_export(df)
    pdf_data = build_pdf_report(selected_city, latest, alerts)
    download_col1, download_col2 = st.columns(2)
    download_col1.download_button(
        "Télécharger CSV",
        data=csv_data,
        file_name=f"meteo_{selected_city.lower()}.csv",
        mime="text/csv",
        key="download_weather_csv",
    )
    download_col2.download_button(
        "Télécharger PDF",
        data=pdf_data,
        file_name=f"rapport_{selected_city.lower()}.pdf",
        mime="application/pdf",
        key="download_weather_pdf",
    )

    # Onglets de visualisation
    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Évolution Météo",
        "🏭 Qualité de l'Air",
        "🗺️ Carte Interactive",
        "🌧️ Précipitations",
    ])

    # Tab1: Évolution météo
    with tab1:
        st.subheader("Évolution des conditions météo")
        fig_temp = px.line(
            df, x="datetime", 
            y=["temperature_2m", "relativehumidity_2m", "windspeed_10m", "surface_pressure"],
            labels={
                "temperature_2m": "Température (°C)",
                "relativehumidity_2m": "Humidité (%)",
                "windspeed_10m": "Vent (km/h)",
                "surface_pressure": "Pression (hPa)",
                "datetime": "Date/Heure",
                "value": "Valeur",
                "variable": "Métrique"
            },
            title="Série temporelle Météo complète"
        )
        fig_temp.update_traces(visible="legendonly", selector={"name": "surface_pressure"})
        st.plotly_chart(fig_temp, use_container_width=True)
    
    # Tab2: Qualité de l'Air
    with tab2:
        st.subheader("Analyse complète de la Qualité de l'Air")
        last_24_hours = DataProcessor.filter_last_24_hours(df)
        if last_24_hours.empty:
            st.info("Aucune donnée disponible sur 24h.")
        else:
            fig_air = px.bar(
                last_24_hours,
                x="datetime",
                y=["us_aqi", "pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide"],
                labels={
                    "us_aqi": "AQI (US)",
                    "pm2_5": "PM2.5",
                    "pm10": "PM10",
                    "nitrogen_dioxide": "NO2",
                    "ozone": "O3",
                    "sulphur_dioxide": "SO2",
                    "carbon_monoxide": "CO",
                    "datetime": "Date/Heure",
                    "value": "Concentration / Indice",
                    "variable": "Polluant"
                },
                barmode="group",
                title="Données de pollution (24h)",
            )
            st.plotly_chart(fig_air, use_container_width=True)

    # Tab3: Carte Interactive
    with tab3:
        st.subheader("Localisation de la station")
        map_df = pd.DataFrame([{
            "lat": city_info["lat"],
            "lon": city_info["lon"],
            "city": selected_city,
            "aqi": latest_aqi
        }])
        fig_map = px.scatter_mapbox(
            map_df, lat="lat", lon="lon", hover_name="city", hover_data=["aqi"],
            color_discrete_sequence=["fuchsia"], zoom=9, height=800
        )
        fig_map.update_layout(mapbox_style="open-street-map")
        st.plotly_chart(fig_map, use_container_width=True)

    # Tab4: Précipitations
    with tab4:
        st.subheader("Radar de précipitations (RainViewer)")
        st.caption("Radar 2h passées + prévision courte. Cliquez sur ▶ Lecture.")
        radar = load_rainviewer_radar()
        if radar is None:
            st.info("Radar indisponible.")
        else:
            frames = build_radar_frames(radar)
            if not frames:
                st.info("Aucune donnée radar.")
            else:
                st.plotly_chart(
                    build_radar_map(
                        selected_city,
                        city_info["lat"],
                        city_info["lon"],
                        radar.get("host", "https://tilecache.rainviewer.com").rstrip("/"),
                        frames,
                    ),
                    use_container_width=True,
                )

if __name__ == "__main__":
    render_dashboard()
