FROM python:3.12-slim

# Évite les fichiers .pyc et permet de voir les logs immédiatement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Installation des dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du projet
COPY . .

# Création du dossier contenant SQLite
RUN mkdir -p /app/data

# Port Streamlit
EXPOSE 8501

# Lancement du dashboard
CMD ["streamlit", "run", "src/dashboard.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]