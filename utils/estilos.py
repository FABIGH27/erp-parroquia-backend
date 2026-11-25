import os
import base64
import streamlit as st

@st.cache_data(show_spinner=False)
def _img_b64(ruta: str) -> str:
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
    html, body, .stApp, [class*="css"], h1, h2, h3, h4, p, label, input, button, textarea, select {
        font-family: "Times New Roman", Times, Georgia, serif !important;
    }
    .stApp {
        background-color: #F5EFE6;
        color: #2E2018;
    }
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
    [data-testid="stForm"], .main [data-testid="stExpander"] {
        background-color: #FFFFFF;
        border-radius: 16px;
        border: 1px solid #EADFD3;
        box-shadow: 0 4px 12px rgba(46, 32, 24, 0.04);
    }
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