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
    # Execution directe : streamlit run src/dashboard.py
    from api_client import WeatherAPIClient, fetch_rainviewer_radar
    from data_processing import DataProcessor
    from alerts import detect_alerts

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DEFAULT_CITIES = {
    "Paris": {"lat": 48.8566, "lon": 2.3522},
    "Lyon": {"lat": 45.7640, "lon": 4.8357},
    "Marseille": {"lat": 43.2965, "lon": 5.3698},
    "Rennes": {"lat": 48.1113, "lon": -1.6800},
    "Grenoble": {"lat": 45.1885, "lon": 5.7245}
}


def build_pdf_report(
    city: str,
    latest: pd.Series,
    alerts: List[Dict[str, str]],
) -> bytes:
    """Build a compact PDF report for the selected city's latest readings."""
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
    """Serialize all displayed readings as an Excel-compatible UTF-8 CSV."""
    return data.to_csv(index=False).encode("utf-8-sig")


# Palette de couleurs des tuiles radar RainViewer.
# 0 = N&B, 1 = Original, 2 = Universal Blue, 3 = TITAN, 4 = The Weather Channel,
# 5 = Meteored, 6 = NEXRAD, 7 = Rainbow SELEX-IS, 8 = Dark Sky.
RAINVIEWER_TILE_COLOR = 4  # The Weather Channel : bon contraste sur le fond OpenStreetMap
# Options de rendu des tuiles (format "smooth_snow") :
#   smooth : lissage des échos radar (0 = brut, 1 = lissé)
#   snow   : affichage des précipitations neigeuses (0 = non, 1 = oui)
RAINVIEWER_TILE_OPTIONS = "0_0"

# Taille des tuiles (en pixels), opacité du calque radar et zoom initial de la carte.
RAINVIEWER_TILE_SIZE = 256
RAINVIEWER_OPACITY = 0.7
RAINVIEWER_ZOOM = 6
# Animation : durée d'affichage d'une frame (ms) et durée de la transition
# entre deux frames (ms). Une transition plus courte que la frame fait
# « glisser » le radar d'une image à l'autre au lieu de sauter.
RAINVIEWER_FRAME_MS = 600
RAINVIEWER_TRANSITION_MS = 250


def build_radar_tile_url(host: str, frame_path: str) -> str:
    """
    Construit le gabarit d'URL des tuiles radar pour une frame donnée.

    RainViewer expose ses images au format
    `{host}{path}/{taille}/{z}/{x}/{y}/{couleur}/{options}.png`. Les jetons
    `{z}/{x}/{y}` sont volontairement laissés tels quels : Plotly les remplacera
    par les coordonnées de tuile correspondant au niveau de zoom courant.

    Args:
        host: Hôte des tuiles fourni par l'API RainViewer (ex. "https://tilecache.rainviewer.com").
        frame_path: Chemin de la frame radar (ex. "/v2/radar/1a2b3c").

    Returns:
        Le gabarit d'URL contenant `{z}`, `{x}` et `{y}`.
    """
    return (
        f"{host.rstrip('/')}{frame_path}/{RAINVIEWER_TILE_SIZE}"
        f"/{{z}}/{{x}}/{{y}}/{RAINVIEWER_TILE_COLOR}/{RAINVIEWER_TILE_OPTIONS}.png"
    )


def build_radar_layer(source: str) -> Dict[str, Any]:
    """
    Décrit le calque raster Plotly d'une frame radar RainViewer.

    Args:
        source: Gabarit d'URL des tuiles (voir `build_radar_tile_url`).

    Returns:
        La description du calque, à placer dans `layout.mapbox.layers`.
    """
    return {
        "sourcetype": "raster",
        "source": [source],
        "sourceattribution": "Radar : RainViewer",
        "opacity": RAINVIEWER_OPACITY,
    }


def build_radar_map(
    city: str,
    lat: float,
    lon: float,
    host: str,
    frames: List[Dict[str, str]],
    height: int = 700,
) -> go.Figure:
    """
    Construit la carte Plotly animée du radar de précipitations.

    Le radar est un *calque raster* (`layout.mapbox.layers`) posé sur un fond de plan
    OpenStreetMap. L'animation utilise le mécanisme natif de Plotly : une `go.Frame`
    par échéance, chacune ne changeant que la source des tuiles radar. Plotly fournit
    alors le bouton Lecture/Pause et le curseur temporel, sans HTML ni JavaScript.

    Args:
        city: Nom de la ville (marqueur au survol).
        lat / lon: Coordonnées du centre de la carte.
        host: Hôte des tuiles radar fourni par l'API RainViewer.
        frames: Liste des échéances produite par `build_radar_frames`.
        height: Hauteur de la figure en pixels.

    Returns:
        Une figure Plotly animée, prête pour `st.plotly_chart`.
    """
    labels = [frame["label"] for frame in frames]
    # Noms de frames indexés : les libellés horaires peuvent se répéter (deux frames
    # à la même minute), alors que les noms référencés par le curseur doivent être uniques.
    frame_names = [f"radar-{index}" for index in range(len(frames))]
    tile_urls = [build_radar_tile_url(host, frame["path"]) for frame in frames]

    station = pd.DataFrame([{"lat": lat, "lon": lon, "ville": city}])
    figure = px.scatter_mapbox(
        station,
        lat="lat",
        lon="lon",
        hover_name="ville",
        zoom=RAINVIEWER_ZOOM,
        height=height,
    )
    figure.update_traces(marker=dict(size=14, color="#d81b60"))
    figure.update_layout(
        mapbox_style="open-street-map",
        # État initial : l'échéance la plus récente (dernière frame de la liste).
        mapbox_layers=[build_radar_layer(tile_urls[-1])],
        margin=dict(l=0, r=0, t=10, b=0),
        # Boutons Lecture / Pause de l'animation.
        updatemenus=[
            {
                "type": "buttons",
                "direction": "left",
                "showactive": False,
                "buttons": [
                    {
                        "label": "▶ Lecture",
                        # args=[None] => rejoue toute la séquence depuis la première frame.
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "frame": {"duration": RAINVIEWER_FRAME_MS, "redraw": True},
                                "transition": {"duration": RAINVIEWER_TRANSITION_MS},
                                "fromcurrent": False,
                                "mode": "immediate",
                            },
                        ],
                    },
                    {
                        "label": "⏸ Pause",
                        "method": "animate",
                        "args": [
                            [None],
                            {
                                "frame": {"duration": 0, "redraw": False},
                                "transition": {"duration": 0},
                                "mode": "immediate",
                            },
                        ],
                    },
                ],
            }
        ],
        # Curseur d'échéance : un pas par frame, avec affichage de l'heure courante.
        sliders=[
            {
                "active": len(frames) - 1,
                "currentvalue": {"prefix": "Échéance : "},
                "steps": [
                    {
                        "label": label,
                        "method": "animate",
                        "args": [
                            [name],
                            {
                                "frame": {"duration": 0, "redraw": True},
                                "transition": {"duration": 0},
                                "mode": "immediate",
                            },
                        ],
                    }
                    for label, name in zip(labels, frame_names)
                ],
            }
        ],
    )

    # Une frame par échéance : seule la source du calque radar change, le fond de plan
    # et le marqueur de la ville restent identiques d'une frame à l'autre.
    figure.frames = [
        go.Frame(
            name=name,
            layout=go.Layout(mapbox=go.layout.Mapbox(layers=[build_radar_layer(url)])),
        )
        for name, url in zip(frame_names, tile_urls)
    ]
    return figure


def build_radar_frames(radar: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Aplatit les frames RainViewer (passé + prévision) en une liste exploitable côté JS.

    RainViewer renvoie deux listes distinctes (`past` et `nowcast`) contenant des
    horodatages Unix. On les convertit ici en libellés horaires lisibles, en
    distinguant les frames observées des frames prévues.

    Returns:
        Une liste de dictionnaires `{"path": <chemin de tuiles>, "label": <HH:MM>}`.
    """
    frames: List[Dict[str, str]] = []
    radar_data = radar.get("radar", {})
    # Frames observées (environ les 2 dernières heures).
    for entry in radar_data.get("past", []):
        frames.append({
            "path": entry["path"],
            "label": datetime.datetime.fromtimestamp(entry["time"]).strftime("%H:%M"),
        })
    # Frames de prévision à courte échéance (nowcast).
    for entry in radar_data.get("nowcast", []):
        frames.append({
            "path": entry["path"],
            "label": datetime.datetime.fromtimestamp(entry["time"]).strftime("%H:%M (prévu)"),
        })
    return frames


@st.cache_data(ttl=300)
def load_rainviewer_radar() -> Optional[Dict[str, Any]]:
    """
    Récupère les métadonnées radar RainViewer, avec mise en cache Streamlit.

    Le cache de 5 minutes évite de rappeler l'API à chaque interaction
    (changement de ville, déplacement du curseur, etc.).
    """
    return fetch_rainviewer_radar()


def render_dashboard():
    """
    Renders Streamlit Web Application Interface.
    """
    st.set_page_config(page_title="Dashboard Météo & AQI", page_icon="🌤️", layout="wide")

    st.title("🌤️ Dashboard Météo & Surveillance Qualité de l'Air")
    st.markdown("Projet 3ᵉ Année Ingénieur — Analyse de données environnementales en temps réel")

    client = WeatherAPIClient()

    # Sidebar Options
    st.sidebar.header("⚙️ Configuration")
    selected_city = st.sidebar.selectbox("Sélectionner une ville", list(DEFAULT_CITIES.keys()))
    mock_mode = st.sidebar.checkbox("Mode Déconnecté / Data Mocked", value=False)

    city_info = DEFAULT_CITIES[selected_city]

    # Fetch Data
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

    # Add calculated metrics
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

    # Alert Box Section
    alerts = detect_alerts(pd.DataFrame([latest]))
    if alerts:
        for alert in alerts:
            if alert["level"] == "danger":
                st.error(f"🚨 **DANGER** : {alert['message']}")
            else:
                st.warning(f"⚠️ **ATTENTION** : {alert['message']}")
    else:
        st.success("✅ Qualité de l'air et conditions météorologiques stables. Aucune alerte active.")

    # KPI Summary Cards
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Température", f"{latest['temperature_2m']:.1f} °C")
    col2.metric("Humidité", f"{latest['relativehumidity_2m']:.0f} %")
    aqi_display = f"{latest_aqi:.0f}" if latest_aqi is not None else "Indisponible"
    col3.metric("Indice AQI (US)", aqi_display)
    col4.metric("PM 2.5", f"{latest['pm2_5']:.1f} µg/m³")
    col5.metric("Score Confort (0-100)", f"{latest['health_score']:.1f}")

    csv_data = build_csv_export(df)
    pdf_data = build_pdf_report(selected_city, latest, alerts)
    download_col1, download_col2 = st.columns(2)
    download_col1.download_button(
        "Télécharger les données CSV",
        data=csv_data,
        file_name=f"meteo_qualite_air_{selected_city.lower()}.csv",
        mime="text/csv",
        key="download_weather_csv",
    )
    download_col2.download_button(
        "Télécharger le rapport PDF",
        data=pdf_data,
        file_name=f"rapport_meteo_qualite_air_{selected_city.lower()}.pdf",
        mime="application/pdf",
        key="download_weather_pdf",
    )

    # Visualizations
    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Évolution Météo",
        "🏭 Qualité de l'Air",
        "🗺️ Carte Interactive",
        "🌧️ Précipitations",
    ])

    with tab1:
        st.subheader("Température et Humidité (7 derniers jours / Prévisions)")
        fig_temp = px.line(
            df, x="datetime", y=["temperature_2m", "relativehumidity_2m"],
            labels={"value": "Valeur", "datetime": "Date/Heure", "variable": "Métrique"},
            title="Série temporelle Météo"
        )
        st.plotly_chart(fig_temp, use_container_width=True)

    with tab2:
        st.subheader("Concentration des Polluants Clés (µg/m³)")
        last_24_hours = DataProcessor.filter_last_24_hours(df)
        if last_24_hours.empty:
            st.info("Aucune donnée mesurée disponible pour les 24 dernières heures.")
        else:
            fig_air = px.bar(
                last_24_hours,
                x="datetime",
                y=["pm2_5", "pm10", "nitrogen_dioxide"],
                barmode="group",
                title="Exposition aux polluants sur les 24 dernières heures",
            )
            st.plotly_chart(fig_air, use_container_width=True)

    with tab3:
        st.subheader("Localisation de la station de suivi")
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

    with tab4:
        st.subheader("Carte des précipitations (radar RainViewer)")
        st.caption(
            "Radar des 2 dernières heures, puis prévision à courte échéance "
            "(source : RainViewer). Cliquez sur ▶ Lecture pour animer le radar, "
            "ou déplacez le curseur pour choisir une échéance."
        )
        radar = load_rainviewer_radar()
        if radar is None:
            # L'API est inaccessible (pas de réseau, service en panne) : on informe sans planter.
            st.info("Radar RainViewer indisponible (réseau ou service momentanément inaccessible).")
        else:
            frames = build_radar_frames(radar)
            if not frames:
                st.info("Aucune image radar disponible pour le moment.")
            else:
                # `host` peut varier selon l'API : on l'utilise en priorité,
                # avec repli sur l'hôte historique de RainViewer.
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
    # Standard Execution runs Streamlit application
    render_dashboard()
