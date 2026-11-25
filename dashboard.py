import streamlit as st
import requests
import pandas as pd
import qrcode
from io import BytesIO
from datetime import datetime, timedelta, timezone
from fpdf import FPDF
import json
import os
import base64
import altair as alt

PERU_TZ = timezone(timedelta(hours=-5))

def ahora_peru() -> datetime:
    return datetime.now(PERU_TZ)

st.set_page_config(page_title="ERP Parroquia - Confirmación", layout="wide")

import base64

def _img_b64(ruta: str) -> tuple:
    carpeta = os.path.dirname(ruta) or "."
    nombre_base = os.path.splitext(os.path.basename(ruta))[0].lower()
    if os.path.isdir(carpeta):
        for archivo in os.listdir(carpeta):
            base_a, ext_a = os.path.splitext(archivo)
            ext_low = ext_a.lower()
            if base_a.lower() == nombre_base and ext_low in [".jpg", ".jpeg", ".png", ".webp"]:
                mime = "image/png" if ext_low == ".png" else ("image/webp" if ext_low == ".webp" else "image/jpeg")
                with open(os.path.join(carpeta, archivo), "rb") as f:
                    return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
    return ""

def mostrar_encabezado_modulo(titulo: str, subtitulo: str, ruta_icono: str):
    uri = _img_b64(ruta_icono)
    icono_html = (
        f'<img src="{uri}" '
        f'style="width:58px; height:58px; object-fit:contain; background:#FFFFFF; padding:4px; border-radius:14px; '
        f'border:2px solid #EADFD3; box-shadow:0 3px 8px rgba(46,32,24,0.12);" />'
        if uri else ""
    )
    html = (
        f'<div style="display:flex; align-items:center; gap:16px; margin-bottom:14px;">'
        f'{icono_html}'
        f'<div>'
        f'<h1 style="margin:0; font-size:2rem; color:#2E2018; line-height:1.15;">{titulo}</h1>'
        f'<p style="margin:4px 0 0 0; color:#7A5C48; font-size:0.95rem;">{subtitulo}</p>'
        f'</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def aplicar_estilo_franciscano():
    st.markdown("""
    <style>
    /* Fuente Times New Roman en todo el sistema */
    html, body, .stApp, [class*="css"], h1, h2, h3, h4, p, label, input, button, textarea, select {
        font-family: "Times New Roman", Times, Georgia, serif !important;
    }

    /* Fondo crema cálido */
    .stApp {
        background-color: #F5EFE6;
        color: #2E2018;
    }

    /* Sidebar café espresso */
    [data-testid="stSidebar"] {
        background-color: #2B1E17;
        border-right: 1px solid #3E2C22;
    }
    [data-testid="stSidebar"] * {
        color: #F5EFE6 !important;
    }
    [data-testid="stSidebar"] .stRadio > div {
        gap: 6px;
    }
    [data-testid="stSidebar"] .stRadio label {
        padding: 8px 12px;
        border-radius: 10px;
        transition: background 0.2s ease;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background-color: #3E2C22;
    }
    [data-testid="stSidebar"] .stRadio label:has(input:checked) {
        background-color: #9C6644 !important;
        font-weight: 600;
    }

    /* Expander de clave temporal y sus inputs dentro del Sidebar */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: #3E2C22 !important;
        border: 1px solid #9C6644 !important;
        border-radius: 12px !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary,
    [data-testid="stSidebar"] [data-testid="stExpander"] summary * {
        color: #F5EFE6 !important;
    }
    [data-testid="stSidebar"] input {
        background-color: #2B1E17 !important;
        color: #F5EFE6 !important;
        border: 1px solid #9C6644 !important;
    }

    /* Botones en el Sidebar (Cerrar sesión / Desbloquear) */
    [data-testid="stSidebar"] .stButton > button {
        background-color: #3E2C22 !important;
        color: #F5EFE6 !important;
        border: 1px solid #9C6644 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #9C6644 !important;
        color: #FFFFFF !important;
    }

    /* Tarjetas de KPIs blancas con sombra suave */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 18px 20px;
        border-radius: 16px;
        border: 1px solid #EADFD3;
        box-shadow: 0 4px 12px rgba(46, 32, 24, 0.05);
    }
    [data-testid="stMetricLabel"] {
        color: #7A5C48 !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        color: #2E2018 !important;
    }

    /* Tarjetas para formularios y expanders del contenido principal */
    [data-testid="stForm"], .main [data-testid="stExpander"] {
        background-color: #FFFFFF;
        border-radius: 16px;
        border: 1px solid #EADFD3;
        box-shadow: 0 4px 12px rgba(46, 32, 24, 0.04);
    }

    /* Notificaciones informativas (st.info) en paleta franciscana */
    [data-testid="stAlert"] {
        background-color: #EFE6DA !important;
        border: 1px solid #D4A373 !important;
        border-left: 5px solid #9C6644 !important;
        border-radius: 12px !important;
        color: #2E2018 !important;
    }
    [data-testid="stAlert"] * {
        color: #2E2018 !important;
    }
    [data-testid="stSidebar"] [data-testid="stAlert"] {
        background-color: #3E2C22 !important;
        border: 1px solid #9C6644 !important;
    }
    [data-testid="stSidebar"] [data-testid="stAlert"] * {
        color: #F5EFE6 !important;
    }

    /* Botones primarios caramelo/tierra */
    .stButton > button[kind="primary"], .stFormSubmitButton > button {
        background-color: #9C6644 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover {
        background-color: #7F4F24 !important;
    }

    /* Pestañas estilo tarjeta */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #EDE3D7;
        border-radius: 10px 10px 0 0;
        padding: 8px 16px;
        color: #4A3528;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #9C6644 !important;
        border-top: 3px solid #9C6644 !important;
    }
    </style>
    """, unsafe_allow_html=True)

aplicar_estilo_franciscano()

API_URL = "https://erp-parroquia-api.onrender.com"

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

GRUPOS_OPCIONES = ["Sin asignar","Grupo Único", "Grupo A", "Grupo B", "Grupo C", "Grupo D"]
SALONES_OPCIONES = ["Sin asignar", "Salón 1", "Salón 2", "Salón 3", "Salón 4"]
LETRAS_AZ = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# =========================================================
# FUNCIONES DE EXPORTACIÓN (EXCEL Y PDF) Y BUSCADOR
# =========================================================
def generar_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Reporte")
    return output.getvalue()

def generar_pdf(df: pd.DataFrame, titulo: str) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    # Encabezado
    pdf.set_font("Helvetica", "B", 14)
    titulo_limpio = titulo.encode("latin-1", "replace").decode("latin-1")
    pdf.cell(0, 10, f"ERP Parroquial - {titulo_limpio}", ln=True, align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(4)

    # Ancho dinámico según número de columnas
    columnas = list(df.columns)
    ancho_util = 277  # A4 horizontal (297mm - 20mm márgenes)
    ancho_col = ancho_util / max(len(columnas), 1)

    # Cabecera de tabla
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    for col in columnas:
        texto = str(col)[:22].encode("latin-1", "replace").decode("latin-1")
        pdf.cell(ancho_col, 7, texto, border=1, fill=True, align="C")
    pdf.ln()

    # Filas
    pdf.set_font("Helvetica", "", 8)
    for _, fila in df.iterrows():
        for col in columnas:
            valor = str(fila[col])[:28].encode("latin-1", "replace").decode("latin-1")
            pdf.cell(ancho_col, 6, valor, border=1, align="L")
        pdf.ln()

    return bytes(pdf.output())

def mostrar_botones_exportacion(df: pd.DataFrame, nombre_base: str, titulo_pdf: str):
    c1, c2, _ = st.columns([1, 1, 3])
    fecha = datetime.now().strftime("%Y%m%d")
    with c1:
        st.download_button(
            label="📊 Descargar Excel",
            data=generar_excel(df),
            file_name=f"{nombre_base}_{fecha}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"xlsx_{nombre_base}"
        )
    with c2:
        st.download_button(
            label="📄 Descargar PDF",
            data=generar_pdf(df, titulo_pdf),
            file_name=f"{nombre_base}_{fecha}.pdf",
            mime="application/pdf",
            key=f"pdf_{nombre_base}"
        )

def selector_con_buscador(etiqueta: str, opciones_dict: dict, key_prefix: str, placeholder: str = "Buscar por DNI, nombre o ID..."):
    filtro = st.text_input(
        f"🔍 Filtrar {etiqueta.lower()}",
        placeholder=placeholder,
        key=f"busq_{key_prefix}"
    )
    if filtro:
        filtradas = {k: v for k, v in opciones_dict.items() if filtro.lower() in k.lower()}
    else:
        filtradas = opciones_dict

    if not filtradas:
        st.warning("No se encontraron coincidencias.")
        return None

    seleccion = st.selectbox(
        f"{etiqueta} ({len(filtradas)} encontrados):",
        list(filtradas.keys()),
        key=f"sel_{key_prefix}"
    )
    return filtradas[seleccion]

# =========================================================
# FUNCIONES DE CARNETS QR (INDIVIDUAL Y EN BLOQUE A4)
# =========================================================
def _limpiar_texto_pdf(texto: str) -> str:
    return str(texto).encode("latin-1", "replace").decode("latin-1")

def _dibujar_carnet(pdf: FPDF, x: float, y: float, alumno: dict):
    ancho, alto = 85, 54

    # Borde guía de recorte
    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, ancho, alto)

    # Franja superior azul
    pdf.set_fill_color(30, 58, 138)
    pdf.rect(x, y, ancho, 11, style="F")

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_xy(x, y + 2.5)
    pdf.cell(ancho, 6, _limpiar_texto_pdf("PARROQUIA - CONFIRMACION"), align="C")

    # Generar imagen QR en memoria
    img_qr = qrcode.make(alumno["QR Token"])
    buf_qr = BytesIO()
    img_qr.save(buf_qr, format="PNG")
    buf_qr.seek(0)
    pdf.image(buf_qr, x=x + 3, y=y + 14, w=34, h=34)

    # Datos del catequizando a la derecha
    pdf.set_text_color(20, 20, 20)
    pdf.set_xy(x + 39, y + 16)
    pdf.set_font("Helvetica", "B", 8)
    pdf.multi_cell(43, 4.2, _limpiar_texto_pdf(alumno["Nombres"].upper()))

    pdf.set_xy(x + 39, y + 26)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(43, 4.2, _limpiar_texto_pdf(alumno["Apellidos"].upper()))

    pdf.set_xy(x + 39, y + 38)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(43, 5, f"DNI: {alumno['DNI']}")

    pdf.set_xy(x + 39, y + 43)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(43, 4, _limpiar_texto_pdf(alumno["QR Token"]))

def generar_carnet_individual_pdf(alumno: dict) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format=(85, 54))
    pdf.set_auto_page_break(False)
    pdf.add_page()
    _dibujar_carnet(pdf, 0, 0, alumno)
    return bytes(pdf.output())

def generar_carnets_bloque_pdf(lista_alumnos: list) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)

    pos_x = [15, 110]               # 2 columnas centradas en A4 (210mm)
    pos_y = [11, 67, 123, 179, 235] # 5 filas en A4 (297mm) = 10 carnets/hoja

    for idx, alumno in enumerate(lista_alumnos):
        pos_en_hoja = idx % 10
        if pos_en_hoja == 0:
            pdf.add_page()
        col = pos_en_hoja % 2
        fila = pos_en_hoja // 2
        _dibujar_carnet(pdf, pos_x[col], pos_y[fila], alumno)

    return bytes(pdf.output())

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
    "📁 Secretaría"
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

# Cajita para que otros roles ingresen una clave temporal
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

st.sidebar.divider()
if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
    st.session_state["admin_logueado"] = False
    st.session_state["admin_info"] = ""
    st.session_state["admin_rol"] = ""
    st.session_state["acceso_temporal"] = False
    st.rerun()

# =========================================================
# SECCIÓN 1: RESUMEN GENERAL (KPIs)
# =========================================================
if pagina == "📊 Resumen General":
    fecha_hoy = ahora_peru().strftime("%d/%m/%Y")
    st.markdown(
        f"""
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-bottom:12px;">
                <div>
                    <div style="color:#7A5C48; font-size:0.95rem;">Paz y Bien, {st.session_state['admin_info']}</div>
                    <h1 style="margin:0; color:#2E2018;">Panel de Confirmación</h1>
                </div>
                <div style="background:#FFFFFF; border:1px solid #EADFD3; border-radius:20px; padding:6px 16px; font-weight:600; color:#4A3528;">
                    📅 {fecha_hoy}
                </div>
            </div>
            """,
        unsafe_allow_html=True,
    )

    b64_portada = _img_b64("assets/portada.jpg")
    if b64_portada:
        st.markdown(
            f'<img src="{b64_portada}" '
            f'style="width:100%; max-height:260px; object-fit:cover; border-radius:18px; '
            f'margin-bottom:18px; box-shadow:0 6px 18px rgba(46,32,24,0.10);" />',
            unsafe_allow_html=True,
        )

    try:
        resp = requests.get(f"{API_URL}/api/v1/dashboard/resumen", timeout=15)
        if resp.status_code == 200:
            datos = resp.json()
            kpis = datos["kpis"]

            f_asis1, f_asis2, _ = st.columns([1.2, 1.2, 2.6])
            modo_asis = f_asis1.selectbox(
                "Filtro de Asistencias Registradas:",
                ["General", "Hoy", "Por fecha"],
                key="kpi_modo_asis"
            )
            fecha_asis_sel = None
            if modo_asis == "Por fecha":
                fecha_asis_sel = f_asis2.date_input(
                    "Selecciona la fecha:",
                    value=ahora_peru().date(),
                    key="kpi_fecha_asis"
                )

            total_asis_mostrar = kpis["total_asistencias_registradas"]
            etiqueta_asis = "Asistencias Registradas (General)"

            if modo_asis in ("Hoy", "Por fecha"):
                fecha_obj = ahora_peru().date() if modo_asis == "Hoy" else fecha_asis_sel
                fecha_iso = fecha_obj.strftime("%Y-%m-%d")
                r_all_asis = requests.get(f"{API_URL}/api/v1/asistencias", timeout=15)
                if r_all_asis.status_code == 200:
                    total_asis_mostrar = sum(
                        1 for a in r_all_asis.json()
                        if str(a.get("Fecha y Hora", "")).startswith(fecha_iso)
                    )
                etiqueta_asis = f"Asistencias ({'Hoy' if modo_asis == 'Hoy' else fecha_obj.strftime('%d/%m/%Y')})"

            col1, col2, col3 = st.columns(3)
            col1.metric("Catequizandos Registrados", kpis["total_catequizandos"])
            col2.metric(etiqueta_asis, total_asis_mostrar)
            col3.metric("Total Recaudado (S/)", f"S/ {kpis['total_recaudado']:.2f}")

            st.divider()
            resp_alertas = requests.get(f"{API_URL}/api/v1/dashboard/alertas", timeout=20)
            alertas = resp_alertas.json() if resp_alertas.status_code == 200 else {}
            deudores = alertas.get("deudores", [])
            docs_pend = alertas.get("documentos_pendientes", [])
            asis_res = alertas.get("asistencias_resumen", [])

            r_conc = requests.get(f"{API_URL}/api/v1/tesoreria/conceptos", timeout=15)
            lista_conceptos = [c["nombre_conc"] for c in r_conc.json()] if r_conc.status_code == 200 else []

            r_docs = requests.get(f"{API_URL}/api/v1/secretaria/documentos", timeout=15)
            lista_docs = [d["nombre_doc"] for d in r_docs.json()] if r_docs.status_code == 200 else []

            total_cat = kpis["total_catequizandos"]


            def _grafico_dona(df_datos: pd.DataFrame, dominio: list, rango_colores: list):
                return (
                    alt.Chart(df_datos)
                    .mark_arc(innerRadius=58, outerRadius=105, stroke="#FFFFFF", strokeWidth=2)
                    .encode(
                        theta=alt.Theta(field="Cantidad", type="quantitative"),
                        color=alt.Color(
                            field="Estado",
                            type="nominal",
                            scale=alt.Scale(domain=dominio, range=rango_colores),
                            legend=alt.Legend(orient="bottom", title=None, labelColor="#2E2018", labelFontSize=13)
                        ),
                        tooltip=["Estado", "Cantidad", "Porcentaje"]
                    )
                    .properties(height=270, background="transparent")
                    .configure_view(strokeWidth=0)
                )


            c1, c2 = st.columns(2)

            # --- GRÁFICO 1: PAGOS POR CONCEPTO ---
            with c1:
                st.subheader("💰 Estado de Pagos por Concepto")
                if lista_conceptos and total_cat > 0:
                    conc_sel = st.selectbox("Selecciona el concepto:", lista_conceptos, key="graf_conc_sel")
                    no_pagaron = sum(1 for d in deudores if d.get("Concepto") == conc_sel)
                    pagaron = max(0, total_cat - no_pagaron)

                    df_g1 = pd.DataFrame([
                        {"Estado": "Pagaron", "Cantidad": pagaron, "Porcentaje": f"{(pagaron / total_cat) * 100:.1f}%"},
                        {"Estado": "Pendientes", "Cantidad": no_pagaron,
                         "Porcentaje": f"{(no_pagaron / total_cat) * 100:.1f}%"},
                    ])
                    st.altair_chart(_grafico_dona(df_g1, ["Pagaron", "Pendientes"], ["#9C6644", "#E6D5C3"]),
                                    use_container_width=True)
                    st.caption(f"**{pagaron}** pagaron • **{no_pagaron}** pendientes (de {total_cat} inscritos)")
                else:
                    st.info("Aún no hay conceptos de pago o catequizandos registrados.")

            # --- GRÁFICO 2: EXPEDIENTES POR DOCUMENTO ---
            with c2:
                st.subheader("📁 Expedientes por Documento")
                if lista_docs and total_cat > 0:
                    doc_sel = st.selectbox("Selecciona el documento requisito:", lista_docs, key="graf_doc_sel")
                    pend_doc = [d for d in docs_pend if d.get("Documento") == doc_sel]
                    observados = sum(1 for d in pend_doc if d.get("Estado") == "Observado")
                    faltantes = len(pend_doc) - observados
                    entregados = max(0, total_cat - len(pend_doc))

                    df_g2 = pd.DataFrame([
                        {"Estado": "Entregado", "Cantidad": entregados,
                         "Porcentaje": f"{(entregados / total_cat) * 100:.1f}%"},
                        {"Estado": "Observado", "Cantidad": observados,
                         "Porcentaje": f"{(observados / total_cat) * 100:.1f}%"},
                        {"Estado": "Pendiente", "Cantidad": faltantes,
                         "Porcentaje": f"{(faltantes / total_cat) * 100:.1f}%"},
                    ])
                    df_g2 = df_g2[df_g2["Cantidad"] > 0]
                    st.altair_chart(
                        _grafico_dona(df_g2, ["Entregado", "Observado", "Pendiente"],
                                      ["#7F4F24", "#D4A373", "#E6D5C3"]),
                        use_container_width=True
                    )
                    st.caption(
                        f"**{entregados}** entregados • **{observados}** observados • **{faltantes}** pendientes")
                else:
                    st.info("Aún no hay documentos requisito o catequizandos registrados.")

            st.divider()
            st.subheader("🚨 Panel de Alertas y Seguimiento")

            if resp_alertas.status_code == 200:
                tab_a1, tab_a2, tab_a3 = st.tabs([
                    f"💸 Pagos Pendientes ({len(deudores)})",
                    f"📄 Docs. Faltantes / Observados ({len(docs_pend)})",
                    "⚠️ Baja Asistencia"
                ])

                with tab_a1:
                    if deudores:
                        df_deu = pd.DataFrame(deudores)
                        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                        conceptos_unicos = ["Todos"] + sorted(df_deu["Concepto"].unique().tolist())
                        filtro_conc = col_f1.selectbox("Concepto:", conceptos_unicos, key="alerta_conc")
                        filtro_col_deu = col_f2.selectbox("Colegio:", ["Todos"] + COLEGIOS_PARROQUIA, key="alerta_col_deu")
                        filtro_grp_deu = col_f3.selectbox("Grupo:", ["Todos"] + GRUPOS_OPCIONES, key="alerta_grp_deu")
                        busq_deu = col_f4.text_input("🔍 DNI o nombre:", key="alerta_busq_deu")

                        if filtro_conc != "Todos":
                            df_deu = df_deu[df_deu["Concepto"] == filtro_conc]
                        if filtro_col_deu != "Todos" and "Colegio" in df_deu.columns:
                            df_deu = df_deu[df_deu["Colegio"] == filtro_col_deu]
                        if filtro_grp_deu != "Todos" and "Grupo" in df_deu.columns:
                            df_deu = df_deu[df_deu["Grupo"] == filtro_grp_deu]
                        if busq_deu:
                            df_deu = df_deu[
                                df_deu.apply(lambda r: busq_deu.lower() in r.astype(str).str.lower().to_string(),
                                             axis=1)]

                        st.metric("Total por Cobrar (filtrado)", f"S/ {df_deu['Debe (S/)'].sum():.2f}")
                        st.dataframe(df_deu, use_container_width=True, hide_index=True)
                        mostrar_botones_exportacion(df_deu, "alerta_deudores", "Reporte de Pagos Pendientes")
                    else:
                        st.success("No hay pagos pendientes.")

                with tab_a2:
                    if docs_pend:
                        df_docs = pd.DataFrame(docs_pend)
                        col_d1, col_d2, col_d3, col_d4, col_d5 = st.columns(5)
                        docs_unicos = ["Todos"] + sorted(df_docs["Documento"].unique().tolist())
                        estados_unicos = ["Todos"] + sorted(df_docs["Estado"].unique().tolist())

                        filtro_doc = col_d1.selectbox("Documento:", docs_unicos, key="alerta_doc")
                        filtro_est = col_d2.selectbox("Estado:", estados_unicos, key="alerta_est")
                        filtro_col_doc = col_d3.selectbox("Colegio:", ["Todos"] + COLEGIOS_PARROQUIA, key="alerta_col_doc")
                        filtro_grp_doc = col_d4.selectbox("Grupo:", ["Todos"] + GRUPOS_OPCIONES, key="alerta_grp_doc")
                        busq_doc = col_d5.text_input("🔍 DNI o nombre:", key="alerta_busq_doc")

                        if filtro_doc != "Todos":
                            df_docs = df_docs[df_docs["Documento"] == filtro_doc]
                        if filtro_est != "Todos":
                            df_docs = df_docs[df_docs["Estado"] == filtro_est]
                        if filtro_col_doc != "Todos" and "Colegio" in df_docs.columns:
                            df_docs = df_docs[df_docs["Colegio"] == filtro_col_doc]
                        if filtro_grp_doc != "Todos" and "Grupo" in df_docs.columns:
                            df_docs = df_docs[df_docs["Grupo"] == filtro_grp_doc]
                        if busq_doc:
                            df_docs = df_docs[
                                df_docs.apply(lambda r: busq_doc.lower() in r.astype(str).str.lower().to_string(),
                                              axis=1)]

                        st.dataframe(df_docs, use_container_width=True, hide_index=True)
                        mostrar_botones_exportacion(df_docs, "alerta_documentos", "Reporte de Documentos Pendientes")
                    else:
                        st.success("Todos los catequizandos tienen sus documentos obligatorios al día.")

                with tab_a3:
                    if asis_res:
                        df_asis = pd.DataFrame(asis_res)
                        col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
                        min_cat = col_s1.number_input("Catequesis menor a:", min_value=0, value=1, step=1)
                        min_misa = col_s2.number_input("Misas menor a:", min_value=0, value=1, step=1)
                        filtro_col_as = col_s3.selectbox("Colegio:", ["Todos"] + COLEGIOS_PARROQUIA, key="alerta_col_asis")
                        filtro_grp_as = col_s4.selectbox("Grupo:", ["Todos"] + GRUPOS_OPCIONES, key="alerta_grp_asis")
                        busq_as = col_s5.text_input("🔍 DNI o nombre:", key="alerta_busq_asis")

                        df_riesgo = df_asis[(df_asis["Catequesis"] < min_cat) | (df_asis["Misas"] < min_misa)]
                        if filtro_col_as != "Todos" and "Colegio" in df_riesgo.columns:
                            df_riesgo = df_riesgo[df_riesgo["Colegio"] == filtro_col_as]
                        if filtro_grp_as != "Todos" and "Grupo" in df_riesgo.columns:
                            df_riesgo = df_riesgo[df_riesgo["Grupo"] == filtro_grp_as]
                        if busq_as:
                            df_riesgo = df_riesgo[
                                df_riesgo.apply(lambda r: busq_as.lower() in r.astype(str).str.lower().to_string(),
                                                axis=1)]

                        st.caption(f"Mostrando **{len(df_riesgo)}** catequizandos por debajo del mínimo configurado.")
                        st.dataframe(df_riesgo, use_container_width=True, hide_index=True)
                        if not df_riesgo.empty:
                            mostrar_botones_exportacion(df_riesgo, "alerta_baja_asistencia",
                                                        "Reporte de Baja Asistencia")
                    else:
                        st.info("Aún no hay catequizandos registrados.")
            else:
                st.warning("No se pudo cargar el panel de alertas.")
        else:
            st.error("No se pudieron cargar las métricas.")
    except Exception as e:
        st.error(f"Error al conectar con Render: {e}")

# =========================================================
# SECCIÓN 1.5: VISUALIZADOR GENERAL (FICHA INTEGRAL)
# =========================================================
elif pagina == "🔎 Visualizador General":
    mostrar_encabezado_modulo(
        "Visualizador General",
        "Ficha integral de datos, asistencias, pagos y documentos",
        "assets/custodia.jpg",
    )
    st.caption("Consulta en un solo lugar los datos personales, asistencias detalladas, pagos y documentos.")

    resp_lista = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
    lista_j = resp_lista.json() if resp_lista.status_code == 200 else []

    if not lista_j:
        st.info("No hay catequizandos registrados aún.")
    else:
        opciones_vis = {
            f"{j['DNI']} - {j['Nombres']} {j['Apellidos']} ({j.get('Colegio', 'Sin asignar')})": j["ID"]
            for j in lista_j
        }
        id_seleccionado = selector_con_buscador(
            "Catequizando",
            opciones_vis,
            "vis_general",
            placeholder="Buscar por DNI, nombre, apellido o colegio..."
        )

        if st.button("🔎 Buscar Ficha", type="primary", key="btn_buscar_ficha"):
            if id_seleccionado:
                st.session_state["ficha_id_actual"] = id_seleccionado

        id_mostrar = st.session_state.get("ficha_id_actual")
        if id_mostrar:
            with st.spinner("Cargando ficha integral..."):
                r_ficha = requests.get(f"{API_URL}/api/v1/catequizandos/{id_mostrar}/ficha-completa", timeout=15)

            if r_ficha.status_code == 200:
                ficha = r_ficha.json()
                datos = ficha["datos"]
                asistencias = ficha["asistencias"]
                pagos_resumen = ficha["pagos"]["resumen"]
                pagos_historial = ficha["pagos"]["historial"]
                documentos = ficha["documentos"]

                st.divider()
                st.subheader(f"👤 {datos['Nombres']} {datos['Apellidos']}")

                # 1. Datos Personales y Contactos
                d1, d2, d3, d4 = st.columns(4)
                d1.markdown(f"**DNI:** {datos['DNI']}\n\n**QR Token:** `{datos['QR Token']}`")
                d2.markdown(
                    f"**Colegio:** {datos['Colegio']}\n\n"
                    f"**Grupo / Salón:** {datos.get('Grupo', 'Sin asignar')} | {datos.get('Salón', 'Sin asignar')}\n\n"
                    f"**Bautismo:** {datos['Bautismo']}"
                )
                d3.markdown(f"**Celular Joven:** {datos['Celular Joven']}")
                d4.markdown(f"**Apoderado 1:** {datos['Apoderado 1']}\n\n**Apoderado 2:** {datos['Apoderado 2']}")

                # Preparar mapas de asistencia por tipo y detalle
                mapa_cat = {a["detalle"]: a for a in asistencias if a["tipo"] == "Catequesis"}
                mapa_misa = {a["detalle"]: a for a in asistencias if a["tipo"] == "Misa"}
                mapa_act = {a["detalle"]: a for a in asistencias if a["tipo"] == "Actividad Parroquial"}

                def construir_tabla_control(lista_items, mapa_reg, nombre_col):
                    filas = []
                    for item in lista_items:
                        reg = mapa_reg.get(item)
                        if reg:
                            icono = "⏰ Tardanza" if reg["estado"] == "Tardanza" else "✅ Presente"
                            filas.append({
                                nombre_col: item,
                                "Estado": icono,
                                "Fecha y Hora": reg["fecha_hora"],
                                "Método": reg["metodo"],
                                "Registrado por": reg["registrado_por"]
                            })
                        else:
                            filas.append({
                                nombre_col: item,
                                "Estado": "❌ Falta",
                                "Fecha y Hora": "-",
                                "Método": "-",
                                "Registrado por": "-"
                            })
                    return pd.DataFrame(filas)

                df_temas = construir_tabla_control(TEMAS_CATEQUESIS, mapa_cat, "Tema")
                df_misas = construir_tabla_control(MISAS_ANUALES, mapa_misa, "Misa")
                df_acts = construir_tabla_control(ACTIVIDADES_PARROQUIALES, mapa_act, "Actividad")

                # KPIs rápidos del alumno
                st.divider()
                k1, k2, k3, k4, k5 = st.columns(5)
                asist_cat = sum(1 for t in TEMAS_CATEQUESIS if t in mapa_cat)
                asist_misa = sum(1 for m in MISAS_ANUALES if m in mapa_misa)
                asist_act = sum(1 for a in ACTIVIDADES_PARROQUIALES if a in mapa_act)
                deuda_total = sum(p["Debe (S/)"] for p in pagos_resumen)
                docs_ok = sum(1 for d in documentos if d["Estado"] == "Entregado")

                k1.metric("📖 Catequesis", f"{asist_cat} / 26")
                k2.metric("⛪ Misas", f"{asist_misa} / 30")
                k3.metric("🎉 Actividades", f"{asist_act} / {len(ACTIVIDADES_PARROQUIALES)}")
                k4.metric("💸 Deuda Total", f"S/ {deuda_total:.2f}")
                k5.metric("📁 Documentos", f"{docs_ok} / {len(documentos)}")

                # Pestañas de detalle completo
                t_cat, t_misa, t_act, t_pagos, t_docs = st.tabs([
                    "📖 Catequesis (Tema por Tema)",
                    "⛪ Misas (Misa por Misa)",
                    "🎉 Actividades",
                    "💰 Pagos",
                    "📁 Documentos"
                ])

                with t_cat:
                    st.dataframe(df_temas, use_container_width=True, hide_index=True)
                    mostrar_botones_exportacion(df_temas, f"catequesis_{datos['DNI']}", f"Catequesis - {datos['Nombres']} {datos['Apellidos']}")

                with t_misa:
                    st.dataframe(df_misas, use_container_width=True, hide_index=True)
                    mostrar_botones_exportacion(df_misas, f"misas_{datos['DNI']}", f"Misas - {datos['Nombres']} {datos['Apellidos']}")

                with t_act:
                    st.dataframe(df_acts, use_container_width=True, hide_index=True)
                    mostrar_botones_exportacion(df_acts, f"actividades_{datos['DNI']}", f"Actividades - {datos['Nombres']} {datos['Apellidos']}")

                with t_pagos:
                    st.markdown("**Resumen por Concepto**")
                    if pagos_resumen:
                        df_pr = pd.DataFrame(pagos_resumen)
                        st.dataframe(df_pr, use_container_width=True, hide_index=True)
                    else:
                        st.info("No hay conceptos de pago configurados.")

                    st.markdown("**Historial de Pagos Realizados**")
                    if pagos_historial:
                        df_ph = pd.DataFrame(pagos_historial)
                        st.dataframe(df_ph, use_container_width=True, hide_index=True)
                        mostrar_botones_exportacion(df_ph, f"pagos_{datos['DNI']}", f"Pagos - {datos['Nombres']} {datos['Apellidos']}")
                    else:
                        st.info("Este catequizando aún no tiene pagos registrados.")

                with t_docs:
                    if documentos:
                        df_d = pd.DataFrame(documentos)
                        st.dataframe(df_d, use_container_width=True, hide_index=True)
                        mostrar_botones_exportacion(df_d, f"documentos_{datos['DNI']}", f"Documentos - {datos['Nombres']} {datos['Apellidos']}")
                    else:
                        st.info("No hay documentos requisito configurados.")
            else:
                st.error(f"No se pudo cargar la ficha ({r_ficha.status_code}): {r_ficha.text}")

# =========================================================
# SECCIÓN 2: DIRECTORIO DE CATEQUIZANDOS
# =========================================================
elif pagina == "👥 Directorio de Catequizandos":
    mostrar_encabezado_modulo(
        "Directorio de Catequizandos",
        "Registro, carnets QR y gestión de jóvenes",
        "assets/san_francisco.jpg",
    )

    with st.expander("➕ Registrar Nuevo Catequizando"):
        with st.form("form_nuevo_catequizando", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            dni_nuevo = c1.text_input("DNI del Joven (8 dígitos) *", max_chars=8)
            nombres_nuevo = c2.text_input("Nombres *")
            apellidos_nuevo = c3.text_input("Apellidos *")

            c4, c5, c6 = st.columns(3)
            colegio_nuevo = c4.selectbox("Colegio", COLEGIOS_PARROQUIA)
            bautismo_nuevo = c5.selectbox("Bautismo", ESTADOS_BAUTISMO)
            cel_joven_nuevo = c6.text_input("Celular del Joven", max_chars=15, placeholder="Ej: 987654321")

            st.markdown("**Contactos de Apoderados (hasta 2)**")
            a1, a2 = st.columns(2)
            cel_ap1_nuevo = a1.text_input("Celular Apoderado 1", max_chars=15, placeholder="Ej: 912345678")
            par_ap1_nuevo = a2.text_input("¿De quién es? (Apoderado 1)", placeholder="Ej: Mamá - María")

            a3, a4 = st.columns(2)
            cel_ap2_nuevo = a3.text_input("Celular Apoderado 2 (Opcional)", max_chars=15)
            par_ap2_nuevo = a4.text_input("¿De quién es? (Apoderado 2 - Opcional)", placeholder="Ej: Papá - Juan")

            btn_guardar = st.form_submit_button("Guardar y Generar QR", type="primary")

            if btn_guardar:
                if not dni_nuevo.strip() or not nombres_nuevo.strip() or not apellidos_nuevo.strip():
                    st.warning("Completa al menos DNI, Nombres y Apellidos.")
                else:
                    resp_crear = requests.post(
                        f"{API_URL}/api/v1/catequizandos",
                        json={
                            "dni": dni_nuevo.strip(),
                            "nombres": nombres_nuevo.strip(),
                            "apellidos": apellidos_nuevo.strip(),
                            "colegio": colegio_nuevo,
                            "estado_bautismo": bautismo_nuevo,
                            "celular_joven": cel_joven_nuevo.strip() or None,
                            "celular_apoderado_1": cel_ap1_nuevo.strip() or None,
                            "parentesco_apoderado_1": par_ap1_nuevo.strip() or None,
                            "celular_apoderado_2": cel_ap2_nuevo.strip() or None,
                            "parentesco_apoderado_2": par_ap2_nuevo.strip() or None,
                        },
                        timeout=15
                    )
                    if resp_crear.status_code in (200, 201):
                        st.success(f"Registrado correctamente. Token QR: {resp_crear.json().get('qr_token', '')}")
                        st.rerun()
                    else:
                        try:
                            msg = resp_crear.json().get("detail", resp_crear.text)
                        except Exception:
                            msg = resp_crear.text
                        st.error(f"Error ({resp_crear.status_code}): {msg}")

    resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
    if resp_jovenes.status_code == 200:
        lista = resp_jovenes.json()
        if lista:
            df = pd.DataFrame(lista)

            # Filtros rápidos (buscador + colegio + bautismo)
            f1, f2, f3 = st.columns([2, 1.2, 1.2])
            busqueda = f1.text_input("🔍 Buscar por DNI, nombre, apellido o celular:", key="busq_cat_dir")
            filtro_colegio = f2.selectbox("Colegio", ["Todos"] + COLEGIOS_PARROQUIA, key="filt_col_dir")
            filtro_bautismo = f3.selectbox("Bautismo", ["Todos"] + ESTADOS_BAUTISMO, key="filt_baut_dir")

            df_filtrado = df.copy()
            if busqueda.strip():
                q = busqueda.strip().lower()
                df_filtrado = df_filtrado[
                    df_filtrado.apply(lambda row: q in row.astype(str).str.lower().to_string(), axis=1)
                ]
            if filtro_colegio != "Todos" and "Colegio" in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado["Colegio"] == filtro_colegio]
            if filtro_bautismo != "Todos" and "Bautismo" in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado["Bautismo"] == filtro_bautismo]

            # Ocultar columnas técnicas *_raw en la tabla y exportación
            cols_visibles = [c for c in df_filtrado.columns if not c.endswith("_raw")]
            df_mostrar = df_filtrado[cols_visibles]

            st.caption(f"Mostrando **{len(df_mostrar)}** de **{len(df)}** catequizandos.")
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            mostrar_botones_exportacion(df_mostrar, "directorio_catequizandos", "Directorio de Catequizandos")

            st.divider()
            st.subheader("🎫 Carnet QR Individual")
            opciones_qr = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j for j in lista}
            alumno_sel = selector_con_buscador("Catequizando para QR", opciones_qr, "qr_cat")

            if alumno_sel:
                img_qr = qrcode.make(alumno_sel["QR Token"])
                buffer = BytesIO()
                img_qr.save(buffer, format="PNG")
                bytes_qr = buffer.getvalue()

                col_img, col_btn = st.columns([1, 2])
                with col_img:
                    st.image(bytes_qr, caption=alumno_sel["QR Token"], width=200)
                with col_btn:
                    st.write(f"**Catequizando:** {alumno_sel['Nombres']} {alumno_sel['Apellidos']}")
                    st.write(f"**DNI:** {alumno_sel['DNI']}")
                    st.write(f"**Colegio:** {alumno_sel.get('Colegio', 'Sin asignar')}")
                    st.write(f"**Bautismo:** {alumno_sel.get('Bautismo', 'Bautizado')}")
                    b1, b2 = st.columns(2)
                    with b1:
                        st.download_button(
                            label="🪪 Descargar Carnet PDF (Pequeño)",
                            data=generar_carnet_individual_pdf(alumno_sel),
                            file_name=f"Carnet_{alumno_sel['DNI']}_{alumno_sel['Apellidos']}.pdf",
                            mime="application/pdf",
                            key=f"pdf_carnet_{alumno_sel['DNI']}"
                        )
                    with b2:
                        st.download_button(
                            label="⬇️ Solo imagen QR (PNG)",
                            data=bytes_qr,
                            file_name=f"QR_{alumno_sel['DNI']}_{alumno_sel['Apellidos']}.png",
                            mime="image/png",
                            key=f"png_qr_{alumno_sel['DNI']}"
                        )

            st.divider()
            with st.expander("🖨️ Impresión de Carnets QR en Bloque (Hoja A4 - 10 por página)"):
                modo_bloque = st.radio(
                    "¿Qué carnets deseas generar?",
                    ["Todos los catequizandos filtrados en la tabla superior", "Seleccionar catequizandos específicos"],
                    horizontal=True,
                    key="modo_bloque_qr"
                )

                alumnos_a_imprimir = []
                if modo_bloque == "Todos los catequizandos filtrados en la tabla superior":
                    dnis_filtrados = set(df_mostrar["DNI"].tolist())
                    alumnos_a_imprimir = [j for j in lista if j["DNI"] in dnis_filtrados]
                else:
                    opciones_multi = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j for j in lista}
                    seleccionados = st.multiselect(
                        "Elige los catequizandos (puedes escribir para buscar):",
                        list(opciones_multi.keys()),
                        key="multi_qr_bloque"
                    )
                    alumnos_a_imprimir = [opciones_multi[s] for s in seleccionados]

                if alumnos_a_imprimir:
                    st.caption(
                        f"Se generarán **{len(alumnos_a_imprimir)}** carnets ({(len(alumnos_a_imprimir) + 9) // 10} hoja(s) A4).")
                    if st.button("⚙️ Preparar PDF en Bloque", key="btn_prep_bloque"):
                        with st.spinner("Generando carnets..."):
                            pdf_bloque = generar_carnets_bloque_pdf(alumnos_a_imprimir)
                        st.download_button(
                            label="📄 Descargar PDF de Carnets A4",
                            data=pdf_bloque,
                            file_name=f"Carnets_QR_Bloque_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            key="btn_dl_bloque"
                        )
                else:
                    st.info("Selecciona al menos un catequizando para generar el PDF.")

            st.divider()
            with st.expander("✏️ Editar o Eliminar Catequizando"):
                opciones_edit = {f"ID {j['ID']} - {j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j for j in lista}
                cat_obj = selector_con_buscador("Catequizando a modificar", opciones_edit, "edit_cat")

                if cat_obj:
                    col_actual = cat_obj.get("Colegio", "Particulares")
                    idx_col = COLEGIOS_PARROQUIA.index(col_actual) if col_actual in COLEGIOS_PARROQUIA else len(COLEGIOS_PARROQUIA) - 1

                    baut_actual = cat_obj.get("Bautismo", "Bautizado")
                    idx_baut = ESTADOS_BAUTISMO.index(baut_actual) if baut_actual in ESTADOS_BAUTISMO else 0

                    with st.form(f"form_editar_cat_{cat_obj['ID']}"):
                        c1, c2, c3 = st.columns(3)
                        edit_dni = c1.text_input("DNI del Joven *", value=cat_obj["DNI"], max_chars=8)
                        edit_nom = c2.text_input("Nombres *", value=cat_obj["Nombres"])
                        edit_ape = c3.text_input("Apellidos *", value=cat_obj["Apellidos"])

                        c4, c5, c6 = st.columns(3)
                        edit_col = c4.selectbox("Colegio", COLEGIOS_PARROQUIA, index=idx_col)
                        edit_baut = c5.selectbox("Bautismo", ESTADOS_BAUTISMO, index=idx_baut)
                        edit_cel_j = c6.text_input("Celular del Joven", value=cat_obj.get("celular_joven_raw", ""), max_chars=15)

                        st.markdown("**Contactos de Apoderados (hasta 2)**")
                        ea1, ea2 = st.columns(2)
                        edit_cel_ap1 = ea1.text_input("Celular Apoderado 1", value=cat_obj.get("celular_apoderado_1_raw", ""), max_chars=15)
                        edit_par_ap1 = ea2.text_input("¿De quién es? (Apoderado 1)", value=cat_obj.get("parentesco_apoderado_1_raw", ""))

                        ea3, ea4 = st.columns(2)
                        edit_cel_ap2 = ea3.text_input("Celular Apoderado 2 (Opcional)", value=cat_obj.get("celular_apoderado_2_raw", ""), max_chars=15)
                        edit_par_ap2 = ea4.text_input("¿De quién es? (Apoderado 2 - Opcional)", value=cat_obj.get("parentesco_apoderado_2_raw", ""))

                        if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                            r_up = requests.put(
                                f"{API_URL}/api/v1/catequizandos/{cat_obj['ID']}",
                                json={
                                    "dni": edit_dni.strip(),
                                    "nombres": edit_nom.strip(),
                                    "apellidos": edit_ape.strip(),
                                    "colegio": edit_col,
                                    "estado_bautismo": edit_baut,
                                    "celular_joven": edit_cel_j.strip() or None,
                                    "celular_apoderado_1": edit_cel_ap1.strip() or None,
                                    "parentesco_apoderado_1": edit_par_ap1.strip() or None,
                                    "celular_apoderado_2": edit_cel_ap2.strip() or None,
                                    "parentesco_apoderado_2": edit_par_ap2.strip() or None,
                                },
                                timeout=15
                            )
                            if r_up.status_code == 200:
                                st.success("Datos actualizados correctamente.")
                                st.rerun()
                            else:
                                st.error(r_up.json().get("detail", "Error al actualizar."))

                    if st.button("🗑️ Eliminar este Catequizando", type="secondary", key=f"btn_del_cat_{cat_obj['ID']}"):
                        r_del = requests.delete(f"{API_URL}/api/v1/catequizandos/{cat_obj['ID']}", timeout=15)
                        if r_del.status_code == 200:
                            st.success("Catequizando eliminado.")
                            st.rerun()
                        else:
                            st.error(r_del.json().get("detail", "No se pudo eliminar."))
        else:
            st.warning("Aún no hay catequizandos registrados.")
    else:
        st.error("No se pudo cargar el directorio.")

# =========================================================
# SECCIÓN 3: CONTROL DE ASISTENCIAS (3 PESTAÑAS)
# =========================================================
elif pagina == "📋 Control de Asistencias":
    mostrar_encabezado_modulo(
        "Control de Asistencias",
        "Seguimiento de los temas, misas y actividades parroquiales",
        "assets/llama.jpg",
    )

    tab1, tab2, tab3 = st.tabs(["📖 Catequesis (26 Temas)", "⛪ Misas (30 Misas)", "🎉 Actividades Parroquiales"])

    def mostrar_tabla_asistencias(tipo_filtro, etiqueta_detalle, opciones_detalle):
        resp = requests.get(
            f"{API_URL}/api/v1/asistencias",
            params={"tipo": tipo_filtro},
            timeout=15
        )
        if resp.status_code == 200:
            registros = resp.json()
            if registros:
                nombre_slug = tipo_filtro.lower().replace(" ", "_")
                df = pd.DataFrame(registros)

                # Renombrar columna 'Actividad' a 'Tema', 'Misa' o 'Actividad'
                if "Actividad" in df.columns:
                    df = df.rename(columns={"Actividad": etiqueta_detalle})

                # Filtros en fila: Buscador + Tema/Misa/Actividad + Colegio
                f1, f2, f3 = st.columns([2, 1.2, 1.2])
                busq_asis = f1.text_input(
                    "🔍 Buscar por DNI, nombre o fecha:",
                    key=f"busq_tabla_asis_{nombre_slug}"
                )
                filtro_det = f2.selectbox(
                    f"Filtrar por {etiqueta_detalle}:",
                    ["Todos"] + opciones_detalle,
                    key=f"filt_det_{nombre_slug}"
                )
                filtro_col = f3.selectbox(
                    "Filtrar por Colegio:",
                    ["Todos"] + COLEGIOS_PARROQUIA,
                    key=f"filt_col_{nombre_slug}"
                )

                # Fila 2 de filtros: Fecha (General / Hoy / Por fecha)
                fd1, fd2, _ = st.columns([1.2, 1.2, 2])
                modo_fecha_tab = fd1.selectbox(
                    "Filtrar por Fecha:",
                    ["General", "Hoy", "Por fecha"],
                    key=f"modo_fecha_{nombre_slug}"
                )
                fecha_tab_sel = None
                if modo_fecha_tab == "Por fecha":
                    fecha_tab_sel = fd2.date_input(
                        "Selecciona la fecha:",
                        value=ahora_peru().date(),
                        key=f"fecha_sel_{nombre_slug}"
                    )

                df_filtrado = df.copy()
                if busq_asis.strip():
                    q = busq_asis.strip().lower()
                    df_filtrado = df_filtrado[
                        df_filtrado.apply(lambda row: q in row.astype(str).str.lower().to_string(), axis=1)
                    ]
                if filtro_det != "Todos" and etiqueta_detalle in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado[etiqueta_detalle] == filtro_det]
                if filtro_col != "Todos" and "Colegio" in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado["Colegio"] == filtro_col]
                if modo_fecha_tab in ("Hoy", "Por fecha") and "Fecha y Hora" in df_filtrado.columns:
                    f_obj = ahora_peru().date() if modo_fecha_tab == "Hoy" else fecha_tab_sel
                    f_iso = f_obj.strftime("%Y-%m-%d")
                    df_filtrado = df_filtrado[
                        df_filtrado["Fecha y Hora"].astype(str).str.startswith(f_iso)
                    ]

                st.caption(f"Mostrando **{len(df_filtrado)}** de **{len(df)}** asistencias.")
                st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
                mostrar_botones_exportacion(df_filtrado, f"asistencias_{nombre_slug}", f"Asistencias - {tipo_filtro}")

                with st.expander("🗑️ Eliminar asistencia duplicada o errónea"):
                    opciones_asis = {
                        f"ID {r['ID']} - {r['Catequizando']} (DNI: {r['DNI']}) | {r.get('Actividad', '-')} | {r['Fecha y Hora']}": r["ID"]
                        for r in registros
                    }
                    id_asis_sel = selector_con_buscador(
                        "Asistencia a eliminar",
                        opciones_asis,
                        f"del_asis_{nombre_slug}",
                        placeholder="Buscar por DNI, nombre, ID o fecha..."
                    )
                    if id_asis_sel and st.button("Eliminar Asistencia", key=f"btn_del_asis_{nombre_slug}"):
                        r_del = requests.delete(f"{API_URL}/api/v1/asistencias/{id_asis_sel}", timeout=15)
                        if r_del.status_code == 200:
                            st.success("Asistencia eliminada.")
                            st.rerun()
                        else:
                            st.error("No se pudo eliminar la asistencia.")
            else:
                st.info(f"No hay asistencias registradas en {tipo_filtro}.")
        else:
            st.error("Error al consultar las asistencias.")

    with tab1:
        mostrar_tabla_asistencias("Catequesis", "Tema", TEMAS_CATEQUESIS)
    with tab2:
        mostrar_tabla_asistencias("Misa", "Misa", MISAS_ANUALES)
    with tab3:
        mostrar_tabla_asistencias("Actividad Parroquial", "Actividad", ACTIVIDADES_PARROQUIALES)

# =========================================================
# SECCIÓN 4: TESORERÍA
# =========================================================
elif pagina == "💰 Tesorería":
    mostrar_encabezado_modulo(
        "Módulo de Tesorería",
        "Control de aportes, conceptos y recaudación",
        "assets/corazon.jpg",
    )

    tab_pagos, tab_conceptos = st.tabs(["💵 Registro de Pagos", "⚙️ Catálogo de Conceptos de Pago"])

    resp_conceptos = requests.get(f"{API_URL}/api/v1/tesoreria/conceptos", timeout=15)
    lista_conceptos = resp_conceptos.json() if resp_conceptos.status_code == 200 else []

    with tab_conceptos:
        st.subheader("Catálogo Anual de Conceptos de Pago")
        with st.form("form_nuevo_concepto", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre_conc = c1.text_input("Nombre del Concepto", placeholder="Ej: Inscripción, Retiro, Ceremonia")
            monto_base = c2.number_input("Monto Base (S/)", min_value=1.0, step=1.0)
            btn_crear_conc = st.form_submit_button("Agregar Concepto")

            if btn_crear_conc:
                if not nombre_conc:
                    st.warning("Ingresa el nombre del concepto.")
                else:
                    r = requests.post(
                        f"{API_URL}/api/v1/tesoreria/conceptos",
                        json={"nombre_conc": nombre_conc.strip(), "monto_base": monto_base},
                        timeout=15
                    )
                    if r.status_code in [200, 201]:
                        st.success("Concepto agregado al catálogo.")
                        st.rerun()
                    else:
                        st.error(f"Error ({r.status_code}): {r.text}")

        if lista_conceptos:
            st.dataframe(pd.DataFrame(lista_conceptos), use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay conceptos de pago registrados para este año.")

    with tab_pagos:
        resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
        lista_jovenes = resp_jovenes.json() if resp_jovenes.status_code == 200 else []

        with st.expander("➕ Registrar Nuevo Pago / Aporte", expanded=True):
            if lista_jovenes and lista_conceptos:
                opciones_j = {
                    f"{j['DNI']} - {j['Nombres']} {j['Apellidos']} ({j.get('Colegio', 'Sin asignar')})": j["DNI"]
                    for j in lista_jovenes
                }
                dni_pago_sel = selector_con_buscador(
                    "Catequizando",
                    opciones_j,
                    "pago_cat",
                    placeholder="Escribe el DNI o nombre del catequizando..."
                )

                with st.form("form_pago", clear_on_submit=True):
                    opciones_c = {
                        f"{c['nombre_conc']} — Monto fijo: S/ {float(c['monto_base']):.2f}": c
                        for c in lista_conceptos
                    }
                    c1, c2, c3 = st.columns(3)
                    concepto_key = c1.selectbox("Concepto de Pago", list(opciones_c.keys()))
                    codigo_boleta = c2.text_input("Código de Boleta Física *", placeholder="Ej: B001-00452")
                    metodo = c3.selectbox("Método de Pago", ["Efectivo", "Yape", "Transferencia"])
                    btn_pago = st.form_submit_button("Registrar Pago", type="primary")

                    if btn_pago:
                        if not dni_pago_sel:
                            st.warning("Selecciona un catequizando.")
                        elif not codigo_boleta.strip():
                            st.warning("Ingresa el código de la boleta física.")
                        else:
                            conc_obj = opciones_c[concepto_key]
                            resp_p = requests.post(
                                f"{API_URL}/api/v1/tesoreria/pagos",
                                json={
                                    "dni_catequizando": dni_pago_sel,
                                    "id_concepto": conc_obj["id_concepto"],
                                    "monto": float(conc_obj["monto_base"]),
                                    "codigo_boleta": codigo_boleta.strip(),
                                    "metodo_pago": metodo,
                                    "id_usuario": st.session_state.get("admin_id", 1)
                                },
                                timeout=15
                            )
                            if resp_p.status_code in [200, 201]:
                                st.success(
                                    f"Pago registrado (S/ {float(conc_obj['monto_base']):.2f} | Boleta: {codigo_boleta.strip()})."
                                )
                                st.rerun()
                            else:
                                st.error(f"Error al registrar pago ({resp_p.status_code}): {resp_p.text}")
            else:
                st.warning("Necesitas tener al menos un catequizando y un concepto de pago en el catálogo.")

        st.subheader("Historial de Pagos")
        resp_pagos = requests.get(f"{API_URL}/api/v1/tesoreria/pagos", timeout=15)
        if resp_pagos.status_code == 200:
            data_pagos = resp_pagos.json()
            lista_pagos = data_pagos.get("pagos", [])
            if lista_pagos:
                df_pagos = pd.DataFrame(lista_pagos)

                p1, p2, p3, p4 = st.columns(4)
                conc_pagos = ["Todos"] + sorted(df_pagos["concepto"].unique().tolist())
                f_conc_p = p1.selectbox("Filtrar por Concepto:", conc_pagos, key="hist_p_conc")
                f_col_p = p2.selectbox("Filtrar por Colegio:", ["Todos"] + COLEGIOS_PARROQUIA, key="hist_p_col")
                f_grp_p = p3.selectbox("Filtrar por Grupo:", ["Todos"] + GRUPOS_OPCIONES, key="hist_p_grp")
                busq_pagos = p4.text_input("🔍 DNI, alumno o boleta:", key="busq_tabla_pagos")

                if f_conc_p != "Todos":
                    df_pagos = df_pagos[df_pagos["concepto"] == f_conc_p]
                if f_col_p != "Todos" and "colegio" in df_pagos.columns:
                    df_pagos = df_pagos[df_pagos["colegio"] == f_col_p]
                if f_grp_p != "Todos" and "grupo" in df_pagos.columns:
                    df_pagos = df_pagos[df_pagos["grupo"] == f_grp_p]
                if busq_pagos:
                    df_pagos = df_pagos[
                        df_pagos.apply(lambda row: busq_pagos.lower() in row.astype(str).str.lower().to_string(), axis=1)
                    ]

                st.metric("Total Recaudado (filtrado)", f"S/ {df_pagos['monto'].sum():.2f}")
                st.dataframe(df_pagos, use_container_width=True, hide_index=True)
                mostrar_botones_exportacion(df_pagos, "reporte_pagos", "Reporte de Tesoreria - Pagos")

                with st.expander("🗑️ Anular / Eliminar un Pago"):
                    opciones_pagos = {
                        f"ID {p['id_pago']} - {p['alumno']} (DNI: {p['dni']}) | {p['concepto']} | Boleta: {p.get('codigo_boleta', '-')} (S/ {p['monto']})": p["id_pago"]
                        for p in lista_pagos
                    }
                    id_pago_sel = selector_con_buscador(
                        "Pago a anular",
                        opciones_pagos,
                        "del_pago",
                        placeholder="Buscar por DNI, alumno, concepto, boleta o ID..."
                    )
                    if id_pago_sel and st.button("Anular Pago Seleccionado", key="btn_del_pago"):
                        r_del = requests.delete(
                            f"{API_URL}/api/v1/tesoreria/pagos/{id_pago_sel}",
                            timeout=15
                        )
                        if r_del.status_code == 200:
                            st.success("Pago anulado correctamente.")
                            st.rerun()
                        else:
                            st.error("No se pudo anular el pago.")
            else:
                st.info("Aún no hay pagos registrados.")
        else:
            st.error("No se pudo cargar el historial de pagos.")

# =========================================================
# SECCIÓN 5: SECRETARÍA
# =========================================================
elif pagina == "📁 Secretaría":
    mostrar_encabezado_modulo(
        "Módulo de Secretaría",
        "Control de expedientes y documentos requisito",
        "assets/corazon.jpg",
    )

    tab_exp, tab_docs = st.tabs(["📋 Control de Expedientes", "⚙️ Catálogo de Documentos Requisito"])

    resp_docs = requests.get(f"{API_URL}/api/v1/secretaria/documentos", timeout=15)
    lista_docs = resp_docs.json() if resp_docs.status_code == 200 else []

    with tab_docs:
        st.subheader("Catálogo Anual de Documentos Requisito")
        with st.form("form_nuevo_doc", clear_on_submit=True):
            c1, c2 = st.columns([3, 1])
            nombre_doc = c1.text_input("Nombre del Documento", placeholder="Ej: Partida de Bautismo, Copia de DNI")
            es_obligatorio = c2.checkbox("Obligatorio", value=True)
            btn_crear_doc = st.form_submit_button("Agregar Documento")

            if btn_crear_doc:
                if not nombre_doc:
                    st.warning("Ingresa el nombre del documento.")
                else:
                    r = requests.post(
                        f"{API_URL}/api/v1/secretaria/documentos",
                        json={"nombre_doc": nombre_doc.strip(), "es_obligatorio": es_obligatorio},
                        timeout=15
                    )
                    if r.status_code in [200, 201]:
                        st.success("Documento agregado al catálogo.")
                        st.rerun()
                    else:
                        st.error(f"Error ({r.status_code}): {r.text}")

        if lista_docs:
            st.dataframe(pd.DataFrame(lista_docs), use_container_width=True, hide_index=True)
            with st.expander("🗑️ Eliminar Documento del Catálogo"):
                opciones_del_doc = {f"{d['nombre_doc']} (ID: {d['id_doc']})": d["id_doc"] for d in lista_docs}
                id_doc_sel = selector_con_buscador("Documento a eliminar", opciones_del_doc, "del_doc", placeholder="Buscar documento...")
                if id_doc_sel and st.button("Eliminar Documento", key="btn_del_doc"):
                    r_del = requests.delete(
                        f"{API_URL}/api/v1/secretaria/documentos/{id_doc_sel}",
                        timeout=15
                    )
                    if r_del.status_code == 200:
                        st.success("Documento eliminado del catálogo.")
                        st.rerun()
                    else:
                        st.error(r_del.json().get("detail", "No se pudo eliminar."))
        else:
            st.info("Aún no hay documentos requisito registrados para este año.")

    with tab_exp:
        resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
        lista_jovenes = resp_jovenes.json() if resp_jovenes.status_code == 200 else []

        with st.expander("📝 Registrar / Actualizar Documento de Catequizando", expanded=True):
            if lista_jovenes and lista_docs:
                with st.form("form_expediente", clear_on_submit=True):
                    opciones_j = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j["DNI"] for j in lista_jovenes}
                    opciones_d = {d["nombre_doc"]: d["id_doc"] for d in lista_docs}

                    c1, c2, c3 = st.columns(3)
                    alumno_sel = c1.selectbox("Catequizando", list(opciones_j.keys()))
                    doc_sel = c2.selectbox("Documento Requisito", list(opciones_d.keys()))
                    estado_exp = c3.selectbox("Estado", ["Entregado", "Pendiente", "Observado"])
                    btn_exp = st.form_submit_button("Guardar Estado")

                    if btn_exp:
                        resp_e = requests.post(
                            f"{API_URL}/api/v1/secretaria/expedientes",
                            json={
                                "dni_catequizando": opciones_j[alumno_sel],
                                "id_doc": opciones_d[doc_sel],
                                "estado": estado_exp,
                                "id_usuario": st.session_state.get("admin_id", 1)
                            },
                            timeout=15
                        )
                        if resp_e.status_code in [200, 201]:
                            st.success("Expediente actualizado correctamente.")
                            st.rerun()
                        else:
                            st.error(f"Error ({resp_e.status_code}): {resp_e.text}")
            else:
                st.warning("Necesitas tener al menos un catequizando y un documento en el catálogo.")

        st.subheader("Consultar Expediente por Catequizando")
        if lista_jovenes:
            opciones_consulta = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j for j in lista_jovenes}
            cat_consulta = selector_con_buscador("Catequizando a consultar", opciones_consulta, "consulta_exp")

            if cat_consulta:
                dni_consulta = cat_consulta["DNI"]
                nombre_consulta = f"{cat_consulta['Nombres']} {cat_consulta['Apellidos']}"
                resp_exp = requests.get(f"{API_URL}/api/v1/secretaria/expedientes/{dni_consulta}", timeout=15)
                if resp_exp.status_code == 200:
                    docs_alumno = resp_exp.json().get("documentos", [])
                    if docs_alumno:
                        df_exp = pd.DataFrame(docs_alumno)
                        st.dataframe(df_exp, use_container_width=True, hide_index=True)
                        mostrar_botones_exportacion(df_exp, f"expediente_{dni_consulta}", f"Expediente - {nombre_consulta}")

                        with st.expander("🗑️ Eliminar Registro de Expediente"):
                            opciones_del_exp = {
                                f"ID {d['id_exp']} - {d['documento']} ({d['estado']})": d["id_exp"]
                                for d in docs_alumno if "id_exp" in d
                            }
                            if opciones_del_exp:
                                id_exp_sel = selector_con_buscador("Registro de expediente a eliminar", opciones_del_exp, "del_exp")
                                if id_exp_sel and st.button("Eliminar Registro", key="btn_del_exp"):
                                    r_del = requests.delete(
                                        f"{API_URL}/api/v1/secretaria/expedientes/{id_exp_sel}",
                                        timeout=15
                                    )
                                    if r_del.status_code == 200:
                                        st.success("Registro de expediente eliminado.")
                                        st.rerun()
                                    else:
                                        st.error(f"No se pudo eliminar ({r_del.status_code}): {r_del.text}")
                    else:
                        st.info("Este catequizando aún no tiene documentos registrados.")
                else:
                    st.error("No se pudo consultar el expediente.")

# =========================================================
# SECCIÓN 5.5: ASIGNACIÓN DE GRUPOS Y SALONES (SOLO ADMIN)
# =========================================================
elif pagina == "🏫 Grupos y Salones":
    mostrar_encabezado_modulo(
        "Asignación de Grupos y Salones",
        "Organiza a los catequizandos por rangos de letras (A–Z) según su apellido o ajústalos manualmente.",
        "assets/paloma.jpg",
    )

    resp_j = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
    lista_j = resp_j.json() if resp_j.status_code == 200 else []

    if not lista_j:
        st.info("Aún no hay catequizandos registrados.")
    else:
        colegio_sel = st.selectbox("1. Selecciona el Colegio:", COLEGIOS_PARROQUIA, key="asig_colegio")
        alumnos_col = [j for j in lista_j if j.get("Colegio") == colegio_sel]
        alumnos_col.sort(key=lambda x: (x.get("Apellidos", "").upper(), x.get("Nombres", "").upper()))

        st.info(f"**{colegio_sel}** tiene actualmente **{len(alumnos_col)}** catequizandos registrados.")

        if alumnos_col:
            tab_az, tab_manual = st.tabs([
                "🔤 Asignación por Rangos de Letras (A–Z)",
                "✏️ Ajuste Manual Rápido (Tabla)"
            ])

            # --- PESTAÑA 1: POR RANGOS DE LETRAS (A-Z) ---
            with tab_az:
                def _letra_inicial(apellido: str) -> str:
                    if not apellido:
                        return "A"
                    c = apellido.strip().upper()[0]
                    reemplazos = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N"}
                    return reemplazos.get(c, c)

                c_modo, c_cant = st.columns(2)
                tipo_asig = c_modo.radio(
                    "¿Qué deseas asignar?",
                    ["Grupo (A, B, C, D)", "Salón (1, 2, 3, 4)"],
                    horizontal=True,
                    key="asig_tipo_az"
                )
                cant_bloques = c_cant.selectbox(
                    "¿En cuántos bloques dividir?",
                    [1, 2, 3, 4],
                    index=0,
                    key="asig_cant_az"
                )

                es_grupo = tipo_asig.startswith("Grupo")
                lista_etiquetas = (
                    ["Grupo A", "Grupo B", "Grupo C", "Grupo D", "Grupo Único"]
                    if es_grupo
                    else ["Salón 1", "Salón 2", "Salón 3", "Salón 4"]
                )

                # Cortes sugeridos por defecto
                cortes_default = {
                    1: [("A", "Z")],
                    2: [("A", "M"), ("N", "Z")],
                    3: [("A", "G"), ("H", "P"), ("Q", "Z")],
                    4: [("A", "F"), ("G", "L"), ("M", "R"), ("S", "Z")],
                }[cant_bloques]

                st.markdown("**Define el grupo/salón y el rango de letras (según la inicial del Apellido):**")
                rangos_config = []
                for idx in range(cant_bloques):
                    r1, r2, r3, r4 = st.columns([1.4, 1, 1, 1.4])
                    etiq = r1.selectbox(
                        "Grupo" if es_grupo else "Salón",
                        lista_etiquetas,
                        index=4 if (es_grupo and cant_bloques == 1) else idx,
                        key=f"az_etiq_{es_grupo}_{cant_bloques}_{idx}"
                    )
                    ini_def, fin_def = cortes_default[idx]
                    l_ini = r2.selectbox(
                        "Desde",
                        LETRAS_AZ,
                        index=LETRAS_AZ.index(ini_def),
                        key=f"az_ini_{cant_bloques}_{idx}"
                    )
                    l_fin = r3.selectbox(
                        "Hasta",
                        LETRAS_AZ,
                        index=LETRAS_AZ.index(fin_def),
                        key=f"az_fin_{cant_bloques}_{idx}"
                    )

                    # Conteo en vivo de cuántos jóvenes caen en este rango
                    coinciden = [
                        a for a in alumnos_col
                        if l_ini <= _letra_inicial(a.get("Apellidos", "")) <= l_fin
                    ]
                    r4.metric("Jóvenes en rango", len(coinciden))
                    rangos_config.append((etiq, l_ini, l_fin, coinciden))

                if st.button("💾 Aplicar Asignación por Letras", type="primary", key="btn_aplicar_az"):
                    payload = []
                    for etiq, _, _, lista_rango in rangos_config:
                        for a in lista_rango:
                            item = {"id_cateq": a["ID"]}
                            if es_grupo:
                                item["grupo"] = etiq
                            else:
                                item["salon"] = etiq
                            payload.append(item)

                    if not payload:
                        st.warning("No hay jóvenes dentro de los rangos seleccionados.")
                    else:
                        r_mas = requests.put(
                            f"{API_URL}/api/v1/admin/catequizandos/asignar-masivo",
                            json=payload,
                            timeout=30
                        )
                        if r_mas.status_code == 200:
                            st.success(r_mas.json().get("mensaje", "Asignación aplicada."))
                            st.rerun()
                        else:
                            st.error(f"Error ({r_mas.status_code}): {r_mas.text}")

            # --- PESTAÑA 2: AJUSTE MANUAL TIPO EXCEL ---
            with tab_manual:
                st.caption("Cambia directamente el Grupo o Salón de cualquier joven y presiona Guardar.")
                df_ed = pd.DataFrame([
                    {
                        "ID": a["ID"],
                        "DNI": a["DNI"],
                        "Apellidos": a["Apellidos"],
                        "Nombres": a["Nombres"],
                        "Grupo": a.get("Grupo", "Sin asignar"),
                        "Salón": a.get("Salón", "Sin asignar"),
                    }
                    for a in alumnos_col
                ])

                df_editado = st.data_editor(
                    df_ed,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["ID", "DNI", "Apellidos", "Nombres"],
                    column_config={
                        "Grupo": st.column_config.SelectboxColumn("Grupo", options=GRUPOS_OPCIONES, required=True),
                        "Salón": st.column_config.SelectboxColumn("Salón", options=SALONES_OPCIONES, required=True),
                    },
                    key=f"editor_gs_{colegio_sel}"
                )

                if st.button("💾 Guardar Cambios Manuales", type="primary", key="btn_guardar_gs_manual"):
                    payload_man = [
                        {
                            "id_cateq": int(row["ID"]),
                            "grupo": row["Grupo"],
                            "salon": row["Salón"],
                        }
                        for _, row in df_editado.iterrows()
                    ]
                    r_man = requests.put(
                        f"{API_URL}/api/v1/admin/catequizandos/asignar-masivo",
                        json=payload_man,
                        timeout=30
                    )
                    if r_man.status_code == 200:
                        st.success(r_man.json().get("mensaje", "Cambios guardados."))
                        st.rerun()
                    else:
                        st.error(f"Error ({r_man.status_code}): {r_man.text}")

# =========================================================
# SECCIÓN 6: ACCESOS TEMPORALES Y CÓDIGOS APK (SOLO ADMIN)
# =========================================================
elif pagina == "🔐 Accesos Temporales":
    st.title("🔐 Accesos Temporales y Turnos APK")

    tab_apk, tab_web = st.tabs([
        "📱 Códigos de Servicio APK (Máx. 4h)",
        "🌐 Claves Temporales Web"
    ])

    # --- PESTAÑA 1: CÓDIGOS DE SERVICIO PARA LA APK ---
    with tab_apk:
        st.subheader("Generar Código de Servicio para Catequistas / Vocales")
        st.caption("El código amarra la APK al evento elegido y cierra la sesión automáticamente al vencer (máx. 4 horas).")

        ACTIVIDADES_PARROQUIALES = [
            "Bienvenida",
            "Corpus Christi",
            "Pollada",
            "Marcha por la Paz",
            "San Francisco de Asis",
            "Retiro Espiritual",
            "Confesión",
            "Ensayo de Ceremonia",
            "Ceremonia"
        ]

        c1, c2 = st.columns(2)
        tipo_srv = c1.selectbox(
            "Evento del turno",
            ["Catequesis", "Misa", "Actividad Parroquial"],
            key="srv_tipo"
        )
        detalle_srv = None
        if tipo_srv == "Catequesis":
            detalle_srv = c2.selectbox("Número de Tema", TEMAS_CATEQUESIS, key="srv_detalle_tema")
        elif tipo_srv == "Misa":
            detalle_srv = c2.selectbox("Número de Misa", MISAS_ANUALES, key="srv_detalle_misa")
        else:
            detalle_srv = c2.selectbox("Actividad específica", ACTIVIDADES_PARROQUIALES, key="srv_detalle_act")

        colegio_srv = st.selectbox(
            "Colegio permitido para este código",
            ["Todos"] + COLEGIOS_PARROQUIA,
            key="srv_colegio"
        )

        c3, c4, c5 = st.columns([1, 1, 1])
        duracion_srv = c3.selectbox("Duración del turno", [1, 2, 3, 4], index=3, format_func=lambda h: f"{h} hora(s)", key="srv_dur")
        usar_tardanza = c4.checkbox("Activar límite de tardanza", value=False, key="srv_chk_tard")
        hora_limite_str = None
        if usar_tardanza:
            hora_lim = c5.time_input("Tardanza a partir de (Hora Perú):", key="srv_hora_lim")
            hora_limite_str = hora_lim.strftime("%H:%M")

        if st.button("🔑 Generar Código de Servicio APK", type="primary", key="btn_gen_srv"):
            r_srv = requests.post(
                f"{API_URL}/api/v1/admin/codigos-servicio",
                json={
                    "tipo_asistencia": tipo_srv,
                    "colegio_permitido": colegio_srv,
                    "detalle_evento": detalle_srv,
                    "duracion_horas": duracion_srv,
                    "hora_limite_tardanza": hora_limite_str
                },
                timeout=15
            )
            if r_srv.status_code == 200:
                d = r_srv.json()
                st.success(
                    f"Código generado: **{d['codigo']}** | Evento: **{d['evento']}** | "
                    f"Tardanza desde: **{d['hora_limite_tardanza']}** | Expira (Perú): **{d['expira_peru']}**"
                )
                st.rerun()
            else:
                st.error(f"Error ({r_srv.status_code}): {r_srv.text}")

        st.divider()
        st.subheader("Códigos de Servicio Recientes")
        resp_srv = requests.get(f"{API_URL}/api/v1/admin/codigos-servicio", timeout=15)
        if resp_srv.status_code == 200 and resp_srv.json():
            lista_srv = resp_srv.json()
            st.dataframe(pd.DataFrame(lista_srv), use_container_width=True, hide_index=True)

            activos_srv = [c for c in lista_srv if c["Estado"] == "Activo"]
            if activos_srv:
                opciones_rev_srv = {
                    f"{c['Código']} - {c['Evento']} (Expira: {c['Expira (Perú)']})": c["ID"]
                    for c in activos_srv
                }
                srv_rev = st.selectbox("Revocar un código activo en vivo:", list(opciones_rev_srv.keys()), key="sel_rev_srv")
                if st.button("🚫 Revocar Código APK Ahora", key="btn_rev_srv"):
                    r_rev = requests.put(
                        f"{API_URL}/api/v1/admin/codigos-servicio/{opciones_rev_srv[srv_rev]}/revocar",
                        timeout=15
                    )
                    if r_rev.status_code == 200:
                        st.success("Código revocado. Cualquier celular usándolo será expulsado al intentar escanear.")
                        st.rerun()
                    else:
                        st.error("No se pudo revocar el código.")
        else:
            st.info("Aún no hay códigos de servicio generados.")

    # --- PESTAÑA 2: CLAVES TEMPORALES PARA EL DASHBOARD WEB ---
    with tab_web:
        st.subheader("Claves Temporales del Dashboard Web")
        st.caption("Genera códigos para que otros roles puedan acceder temporalmente a todos los módulos web.")

        with st.form("form_clave_temporal"):
            duracion_map = {
                "24 horas": "24h",
                "48 horas": "48h",
                "1 semana (7 días)": "7d",
                "Indeterminado (hasta revocar)": "indeterminado"
            }
            seleccion_dur = st.selectbox("Duración de la clave", list(duracion_map.keys()))
            if st.form_submit_button("Generar Nueva Clave"):
                r = requests.post(
                    f"{API_URL}/api/v1/admin/claves-temporales",
                    json={"duracion": duracion_map[seleccion_dur]},
                    timeout=15
                )
                if r.status_code == 200:
                    data = r.json()
                    st.success(f"Clave generada: **{data['codigo']}** (Expira: {data['expira']})")
                    st.rerun()
                else:
                    st.error(f"Error: {r.text}")

        st.divider()
        st.subheader("Claves Registradas")
        resp_claves = requests.get(f"{API_URL}/api/v1/admin/claves-temporales", timeout=15)
        if resp_claves.status_code == 200 and resp_claves.json():
            claves = resp_claves.json()
            st.dataframe(pd.DataFrame(claves), use_container_width=True, hide_index=True)

            activas = [c for c in claves if c["Estado"] == "Activa"]
            if activas:
                opciones_rev = {f"{c['Código']} (Expira: {c['Expira (UTC)']})": c["ID"] for c in activas}
                clave_rev = st.selectbox("Revocar una clave activa:", list(opciones_rev.keys()))
                if st.button("🚫 Revocar Clave Seleccionada"):
                    r_rev = requests.put(
                        f"{API_URL}/api/v1/admin/claves-temporales/{opciones_rev[clave_rev]}/revocar",
                        timeout=15
                    )
                    if r_rev.status_code == 200:
                        st.success("Clave revocada.")
                        st.rerun()
        else:
            st.info("No hay claves temporales generadas aún.")

# =========================================================
# SECCIÓN 7: GESTIÓN DE USUARIOS (SOLO ADMIN)
# =========================================================
elif pagina == "👤 Gestión de Usuarios":
    st.title("👤 Gestión de Usuarios del Sistema")
    st.caption("Crea y administra las cuentas del equipo parroquial.")

    with st.expander("➕ Crear Nuevo Usuario", expanded=True):
        with st.form("form_nuevo_usuario", clear_on_submit=True):
            c1, c2 = st.columns(2)
            dni_u = c1.text_input("DNI (8 dígitos)", max_chars=8)
            nombre_u = c2.text_input("Nombre Completo")

            c3, c4 = st.columns(2)
            pass_u = c3.text_input("Contraseña", type="password")
            rol_u = c4.selectbox(
                "Rol asignado",
                ["Vocal", "Catequista", "Secretario", "Tesorero", "Coordinador", "Administrador"]
            )

            if st.form_submit_button("Crear Usuario"):
                if not dni_u or not nombre_u or not pass_u:
                    st.warning("Completa todos los campos.")
                else:
                    r = requests.post(
                        f"{API_URL}/api/v1/admin/usuarios",
                        json={
                            "dni": dni_u,
                            "nombre": nombre_u,
                            "password": pass_u,
                            "rol": rol_u
                        },
                        timeout=15
                    )
                    if r.status_code in [200, 201]:
                        st.success(f"Usuario **{nombre_u}** ({rol_u}) creado correctamente.")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", f"Error ({r.status_code}): {r.text}"))

    st.divider()
    st.subheader("Usuarios Registrados")
    resp_u = requests.get(f"{API_URL}/api/v1/admin/usuarios", timeout=15)
    if resp_u.status_code == 200 and resp_u.json():
        usuarios = resp_u.json()
        st.dataframe(pd.DataFrame(usuarios), use_container_width=True, hide_index=True)

        opciones_del = {f"{u['Nombre']} - {u['Rol']} (DNI: {u['DNI']})": u["ID"] for u in usuarios}
        id_u_eliminar = selector_con_buscador("Usuario a eliminar", opciones_del, "del_usuario", placeholder="Buscar por DNI, nombre o rol...")
        if id_u_eliminar and st.button("🗑️ Eliminar Usuario Seleccionado"):
            r_del = requests.delete(
                f"{API_URL}/api/v1/admin/usuarios/{id_u_eliminar}",
                timeout=15
            )
            if r_del.status_code == 200:
                st.success("Usuario eliminado.")
                st.rerun()
            else:
                st.error(f"No se pudo eliminar ({r_del.status_code}): {r_del.text}")
    else:
        st.info("No hay usuarios registrados.")

# =========================================================
# SECCIÓN 8: RESPALDO Y RESTAURACIÓN (SOLO ADMIN)
# =========================================================
elif pagina == "💾 Respaldo y Restauración":
    st.title("💾 Respaldo y Restauración de Base de Datos")
    st.caption("Descarga copias de seguridad completas o restaura el sistema ante cualquier imprevisto.")

    tab_bk, tab_rest, tab_imp = st.tabs([
        "📦 Descargar Copia de Seguridad",
        "♻️ Restaurar desde Backup (.json)",
        "📥 Importar Catequizandos (.xlsx)"
    ])

    with tab_bk:
        st.subheader("Generar Respaldo Completo")
        st.write(
            "- **Backup Técnico (`.json`):** Sirve para restaurar exactamente toda la base de datos (roles, usuarios, catequizandos, asistencias, pagos y expedientes).\n"
            "- **Respaldo Legible (`.xlsx`):** Archivo Excel con todas las tablas en pestañas separadas para archivo local."
        )

        if st.button("🔄 Generar Copia de Seguridad Ahora", type="primary"):
            with st.spinner("Extrayendo todas las tablas desde TiDB Cloud..."):
                r_bk = requests.get(f"{API_URL}/api/v1/admin/backup/exportar", timeout=30)

            if r_bk.status_code == 200:
                backup_data = r_bk.json()
                fecha_tag = datetime.now().strftime("%Y%m%d_%H%M")

                # 1. JSON técnico para restauración
                json_bytes = json.dumps(backup_data, indent=2, ensure_ascii=False).encode("utf-8")

                # 2. Excel multi-hoja legible
                excel_buf = BytesIO()
                with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
                    for tabla in [
                        "catequizandos", "asistencias", "pagos",
                        "expedientes", "conceptos_pago", "documentos_requisito",
                        "usuarios", "roles"
                    ]:
                        df_t = pd.DataFrame(backup_data.get(tabla, []))
                        df_t.to_excel(writer, index=False, sheet_name=tabla[:31])
                excel_bytes = excel_buf.getvalue()

                st.success("Copia de seguridad generada correctamente.")
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button(
                        label="⬇️ Descargar Backup Técnico (.json)",
                        data=json_bytes,
                        file_name=f"backup_erp_parroquia_{fecha_tag}.json",
                        mime="application/json"
                    )
                with c2:
                    st.download_button(
                        label="📊 Descargar Respaldo Completo (.xlsx)",
                        data=excel_bytes,
                        file_name=f"respaldo_erp_parroquia_{fecha_tag}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.error(f"Error al generar respaldo ({r_bk.status_code}): {r_bk.text}")

    with tab_rest:
        st.subheader("Restaurar Base de Datos desde Archivo `.json`")
        st.warning("Esta operación inserta los registros faltantes respetando sus IDs y relaciones originales. Los registros que ya existan en la base de datos se omiten sin sobrescribirse.")

        archivo_json = st.file_uploader("Selecciona tu archivo backup_erp_parroquia_*.json", type=["json"])
        if archivo_json is not None:
            try:
                contenido = json.loads(archivo_json.read().decode("utf-8"))
                st.info(
                    f"**Fecha del respaldo:** {contenido.get('fecha_backup', 'Desconocida')} | "
                    f"**Catequizandos:** {len(contenido.get('catequizandos', []))} | "
                    f"**Asistencias:** {len(contenido.get('asistencias', []))} | "
                    f"**Pagos:** {len(contenido.get('pagos', []))}"
                )
                confirmar = st.checkbox("Confirmo que deseo restaurar estos datos en la base de datos actual.")
                if confirmar and st.button("♻️ Iniciar Restauración", type="primary"):
                    with st.spinner("Restaurando tablas en orden de dependencias..."):
                        r_res = requests.post(
                            f"{API_URL}/api/v1/admin/backup/restaurar",
                            json=contenido,
                            timeout=60
                        )
                    if r_res.status_code == 200:
                        st.success("¡Restauración completada!")
                        st.json(r_res.json().get("registros_restaurados", {}))
                    else:
                        st.error(f"Error ({r_res.status_code}): {r_res.text}")
            except Exception as e:
                st.error(f"Archivo JSON inválido: {e}")

    with tab_imp:
        st.subheader("Importación Masiva de Catequizandos desde Excel")
        st.caption("El archivo Excel debe tener exactamente las columnas: **DNI**, **Nombres**, **Apellidos**.")

        # Plantilla descargable
        df_plantilla = pd.DataFrame([
            {"DNI": "12345678", "Nombres": "Juan Carlos", "Apellidos": "Perez Quispe"}
        ])
        st.download_button(
            label="📄 Descargar Plantilla Excel de Ejemplo",
            data=generar_excel(df_plantilla),
            file_name="plantilla_catequizandos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        archivo_xlsx = st.file_uploader("Sube tu archivo Excel (.xlsx)", type=["xlsx"])
        if archivo_xlsx is not None:
            try:
                df_imp = pd.read_excel(archivo_xlsx, dtype={"DNI": str})
                columnas_req = {"DNI", "Nombres", "Apellidos"}
                if not columnas_req.issubset(set(df_imp.columns)):
                    st.error("El Excel debe contener las columnas exactas: DNI, Nombres, Apellidos.")
                else:
                    st.dataframe(df_imp.head(20), use_container_width=True, hide_index=True)
                    st.caption(f"Total de filas detectadas: **{len(df_imp)}**")
                    if st.button("📥 Importar Catequizandos", type="primary"):
                        payload = [
                            {
                                "dni": str(row["DNI"]).strip().zfill(8),
                                "nombres": str(row["Nombres"]).strip(),
                                "apellidos": str(row["Apellidos"]).strip()
                            }
                            for _, row in df_imp.dropna(subset=["DNI", "Nombres", "Apellidos"]).iterrows()
                        ]
                        with st.spinner("Importando catequizandos..."):
                            r_imp = requests.post(
                                f"{API_URL}/api/v1/admin/importar/catequizandos",
                                json=payload,
                                timeout=60
                            )
                        if r_imp.status_code == 200:
                            res = r_imp.json()
                            st.success(f"Importación terminada: **{res['creados']}** creados, **{res['omitidos']}** omitidos (duplicados o DNI inválido).")
                        else:
                            st.error(f"Error ({r_imp.status_code}): {r_imp.text}")
            except Exception as e:
                st.error(f"No se pudo leer el archivo Excel: {e}")