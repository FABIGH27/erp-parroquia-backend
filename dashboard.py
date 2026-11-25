import requests
import streamlit as st

st.set_page_config(page_title="ERP Parroquia - Confirmación", layout="wide")

from utils.api import API_URL
from utils.estilos import _img_b64, aplicar_estilo_franciscano
from views.resumen import mostrar_resumen
from views.visualizador import mostrar_visualizador
from views.directorio import mostrar_directorio
from views.asistencias import mostrar_asistencias
from views.tesoreria import mostrar_tesoreria
from views.secretaria import mostrar_secretaria
from views.grupos import mostrar_grupos
from views.admin import (
    mostrar_accesos_temporales,
    mostrar_gestion_usuarios,
    mostrar_respaldo,
)

aplicar_estilo_franciscano()

# Estado de sesión global
if "admin_logueado" not in st.session_state:
    st.session_state["admin_logueado"] = False
    st.session_state["admin_info"] = ""
    st.session_state["admin_rol"] = ""
    st.session_state["admin_id"] = 1

if "acceso_temporal" not in st.session_state:
    st.session_state["acceso_temporal"] = False

# =========================================================
# PANTALLA DE INICIO DE SESIÓN GENERAL
# =========================================================
if not st.session_state["admin_logueado"]:
    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    with col_centro:
        b64_portada = _img_b64("assets/portada.jpg")
        if b64_portada:
            st.markdown(
                f'<img src="{b64_portada}" '
                f'style="width:100%; border-radius:18px; margin-bottom:14px; '
                f'box-shadow:0 6px 18px rgba(46,32,24,0.14);" />',
                unsafe_allow_html=True,
            )
        st.markdown(
            "<h3 style='text-align:center; color:#2E2018; margin-bottom:2px;'>🔒 Inicio de Sesión Administrativo</h3>"
            "<p style='text-align:center; color:#7A5C48; font-size:0.9rem;'>Ingresa con tu cuenta de Coordinador, Secretario, Tesorero, Vocal o Catequista.</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_general_form"):
            dni_input = st.text_input("DNI de Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            btn_ingresar = st.form_submit_button("Ingresar al Sistema", use_container_width=True)

            if btn_ingresar:
                try:
                    resp = requests.post(
                        f"{API_URL}/api/v1/admin/login",
                        json={"dni": dni_input, "password": pass_input},
                        timeout=15
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state["admin_logueado"] = True
                        st.session_state["admin_info"] = f"{data['usuario']} ({data['rol']})"
                        st.session_state["admin_rol"] = data["rol"]
                        st.session_state["admin_id"] = data.get("id_usuario", 1)
                        st.session_state["acceso_temporal"] = False
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "Credenciales inválidas."))
                except Exception as e:
                    st.error(f"Error de conexión con la API: {e}")

    st.stop()

# =========================================================
# MENÚ LATERAL (SIDEBAR) CON PERMISOS POR ROL (RBAC)
# =========================================================
b64_tau = _img_b64("assets/tau.jpg")
if b64_tau:
    st.sidebar.markdown(
        f"""
        <div style="text-align:center; padding:8px 0 12px 0;">
            <img src="{b64_tau}"
                style="width:92px; height:92px; object-fit:cover; border-radius:50%;
                    border:2px solid #9C6644; background:#FFFFFF; padding:4px;" />
            <div style="font-size:1.15rem; font-weight:700; margin-top:8px;">Confirmación</div>
            <div style="font-size:0.8rem; opacity:0.8;">Paz y Bien • ERP Parroquial</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.sidebar.title("⛪ ERP Parroquia")

st.sidebar.markdown(
    f'<div style="background-color:#3E2C22; border:1px solid #9C6644; border-radius:12px; '
    f'padding:10px 14px; color:#F5EFE6; font-weight:600; font-size:0.95rem; margin-bottom:12px;">'
    f'👤 {st.session_state["admin_info"]}</div>',
    unsafe_allow_html=True,
)

rol_actual = st.session_state.get("admin_rol", "").strip().lower()
es_admin = rol_actual in ["administrador", "admin", "coordinador"]

TODOS_LOS_MODULOS = [
    "📊 Resumen General",
    "🔎 Visualizador General",
    "👥 Directorio de Catequizandos",
    "📋 Control de Asistencias",
    "💰 Tesorería",
    "📁 Secretaría",
]

PERMISOS_POR_ROL = {
    "administrador": TODOS_LOS_MODULOS + ["🏫 Grupos y Salones", "🔐 Accesos Temporales", "👤 Gestión de Usuarios", "💾 Respaldo y Restauración"],
    "admin": TODOS_LOS_MODULOS + ["🏫 Grupos y Salones", "🔐 Accesos Temporales", "👤 Gestión de Usuarios", "💾 Respaldo y Restauración"],
    "coordinador": TODOS_LOS_MODULOS + ["🏫 Grupos y Salones", "🔐 Accesos Temporales", "👤 Gestión de Usuarios", "💾 Respaldo y Restauración"],
    "vocal": ["📊 Resumen General", "🔎 Visualizador General", "👥 Directorio de Catequizandos", "📋 Control de Asistencias"],
    "tesorero": ["📊 Resumen General", "💰 Tesorería"],
    "tesorera": ["📊 Resumen General", "💰 Tesorería"],
    "secretario": ["📊 Resumen General", "🔎 Visualizador General", "👥 Directorio de Catequizandos", "📁 Secretaría"],
    "secretaria": ["📊 Resumen General", "🔎 Visualizador General", "👥 Directorio de Catequizandos", "📁 Secretaría"],
    "catequista": ["🔎 Visualizador General", "👥 Directorio de Catequizandos", "📋 Control de Asistencias"],
}

if st.session_state["acceso_temporal"]:
    opciones_menu = TODOS_LOS_MODULOS
else:
    opciones_menu = PERMISOS_POR_ROL.get(rol_actual, ["📊 Resumen General"])

pagina = st.sidebar.radio("Navegación", opciones_menu)

if not es_admin:
    st.sidebar.divider()
    if st.session_state["acceso_temporal"]:
        st.sidebar.info("🔓 Acceso temporal activo")
    else:
        with st.sidebar.expander("🔑 ¿Tienes clave temporal?"):
            clave_ingresada = st.text_input("Código temporal", placeholder="Ej: TMP-A1B2C3")
            if st.button("Desbloquear módulos", use_container_width=True):
                try:
                    r = requests.post(
                        f"{API_URL}/api/v1/admin/validar-clave-temporal",
                        json={"codigo": clave_ingresada},
                        timeout=15
                    )
                    if r.status_code == 200:
                        st.session_state["acceso_temporal"] = True
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Clave inválida."))
                except Exception as e:
                    st.error(f"Error de conexión: {e}")

if st.sidebar.button("🔄 Actualizar datos", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
    st.session_state["admin_logueado"] = False
    st.session_state["admin_info"] = ""
    st.session_state["admin_rol"] = ""
    st.session_state["acceso_temporal"] = False
    st.rerun()

# =========================================================
# ENRUTADOR DE VISTAS
# =========================================================
RUTAS = {
    "📊 Resumen General": mostrar_resumen,
    "🔎 Visualizador General": mostrar_visualizador,
    "👥 Directorio de Catequizandos": mostrar_directorio,
    "📋 Control de Asistencias": mostrar_asistencias,
    "💰 Tesorería": mostrar_tesoreria,
    "📁 Secretaría": mostrar_secretaria,
    "🏫 Grupos y Salones": mostrar_grupos,
    "🔐 Accesos Temporales": mostrar_accesos_temporales,
    "👤 Gestión de Usuarios": mostrar_gestion_usuarios,
    "💾 Respaldo y Restauración": mostrar_respaldo,
}

RUTAS[pagina]()