import logging

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from .api_client import WeatherAPIClient
    from .data_processing import DataProcessor
    from .alerts import detect_alerts
except ImportError:
    # Execution directe : streamlit run src/dashboard.py
    from api_client import WeatherAPIClient
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


def render_dashboard():
    """
    Renders Streamlit Web Application Interface.
    Author: Student C (Lead UI/UX)
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
        raw_data = client.fetch_weather_and_air_quality(city_info["lat"], city_info["lon"], mock_mode=mock_mode)
        df = DataProcessor.process_raw_api_data(raw_data)

    if df.empty:
        st.error("Impossible de récupérer ou d'afficher les données.")
        return

    # Add calculated metrics
    df["health_score"] = DataProcessor.calculate_custom_health_index(df)
    latest = df.iloc[-1]
    aqi_values = pd.to_numeric(df["us_aqi"], errors="coerce").dropna()
    latest_aqi = aqi_values.iloc[-1] if not aqi_values.empty else None

    # Alert Box Section
    alerts = detect_alerts(df)
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

    # Visualizations
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📈 Évolution Météo", "🏭 Qualité de l'Air", "🗺️ Carte Interactive"])

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
        fig_air = px.bar(
            df.tail(24), x="datetime", y=["pm2_5", "pm10", "nitrogen_dioxide"],
            barmode="group",
            title="Exposition aux polluants sur les 24 dernières heures"
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
            color_discrete_sequence=["fuchsia"], zoom=9, height=400
        )
        fig_map.update_layout(mapbox_style="open-street-map")
        st.plotly_chart(fig_map, use_container_width=True)


if __name__ == "__main__":
    # Standard Execution runs Streamlit application
    render_dashboard()
