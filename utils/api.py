import requests
import streamlit as st
from datetime import datetime, timedelta, timezone

API_URL = "https://erp-parroquia-api.onrender.com"
PERU_TZ = timezone(timedelta(hours=-5))

def ahora_peru() -> datetime:
    return datetime.now(PERU_TZ)

@st.cache_resource
def get_http_session():
    return requests.Session()

@st.cache_data(ttl=45, show_spinner=False)
def _api_get_cached(ruta: str, params=None):
    r = get_http_session().get(f"{API_URL}{ruta}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def api_get(ruta: str, params=None):
    try:
        return _api_get_cached(ruta, params)
    except Exception:
        return None

COLEGIOS_PARROQUIA = [
    "Mercedes",
    "Politécnico",
    "Santa Mónica",
    "César Vallejo",
    "San Francisco de Borja",
    "Particulares",
]

ESTADOS_BAUTISMO = ["Bautizado", "Por bautizar"]
TEMAS_CATEQUESIS = [f"Tema {i}" for i in range(1, 27)]
MISAS_ANUALES = [f"Misa {i}" for i in range(1, 31)]
ACTIVIDADES_PARROQUIALES = [
    "Bienvenida",
    "Corpus Christi",
    "Pollada",
    "Marcha por la Paz",
    "San Francisco de Asis",
    "Retiro Espiritual",
    "Confesión",
    "Ensayo de Ceremonia",
    "Ceremonia",
]

GRUPOS_OPCIONES = ["Sin asignar", "Grupo Único", "Grupo A", "Grupo B", "Grupo C", "Grupo D"]
SALONES_OPCIONES = ["Sin asignar", "Salón 1", "Salón 2", "Salón 3", "Salón 4"]
LETRAS_AZ = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")