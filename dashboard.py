import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="ERP Parroquia - Confirmación", layout="wide")

API_URL = "https://erp-parroquia-api.onrender.com"

# Estado de sesión para el login administrativo
if "admin_logueado" not in st.session_state:
    st.session_state["admin_logueado"] = False
    st.session_state["admin_info"] = ""

# =========================================================
# MENÚ LATERAL (SIDEBAR)
# =========================================================
st.sidebar.title("⛪ ERP Parroquia")
pagina = st.sidebar.radio(
    "Navegación",
    ["📊 Resumen General", "👥 Directorio de Catequizandos", "📋 Control de Asistencias"]
)

if st.session_state["admin_logueado"]:
    st.sidebar.divider()
    st.sidebar.success(f"Sesión: {st.session_state['admin_info']}")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state["admin_logueado"] = False
        st.session_state["admin_info"] = ""
        st.rerun()

# Función reutilizable para pedir login en secciones restringidas
def mostrar_login_admin():
    st.info("🔒 Inicia sesión con credenciales de Coordinador, Secretario o Tesorero.")
    with st.form("login_admin_form"):
        dni_input = st.text_input("DNI de Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        btn_ingresar = st.form_submit_button("Ingresar")

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
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Credenciales inválidas."))
            except Exception as e:
                st.error(f"Error de conexión con la API: {e}")

# =========================================================
# SECCIÓN 1: RESUMEN GENERAL (KPIs)
# =========================================================
if pagina == "📊 Resumen General":
    st.title("📊 Dashboard Administrativo - Confirmación")

    try:
        resp = requests.get(f"{API_URL}/api/v1/dashboard/resumen", timeout=15)
        if resp.status_code == 200:
            datos = resp.json()
            kpis = datos["kpis"]

            col1, col2, col3 = st.columns(3)
            col1.metric("Catequizandos Registrados", kpis["total_catequizandos"])
            col2.metric("Asistencias Registradas", kpis["total_asistencias_registradas"])
            col3.metric("Total Recaudado (S/)", f"S/ {kpis['total_recaudado']:.2f}")

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Recaudación por Método de Pago")
                if datos["recaudacion_por_metodo"]:
                    st.bar_chart(datos["recaudacion_por_metodo"])
                else:
                    st.caption("Sin pagos registrados aún.")
            with c2:
                st.subheader("Estado de Expedientes")
                if datos["estado_expedientes"]:
                    st.bar_chart(datos["estado_expedientes"])
                else:
                    st.caption("Sin expedientes registrados aún.")
        else:
            st.error("No se pudieron cargar las métricas.")
    except Exception as e:
        st.error(f"Error al conectar con Render: {e}")

# =========================================================
# SECCIÓN 2: DIRECTORIO DE CATEQUIZANDOS
# =========================================================
elif pagina == "👥 Directorio de Catequizandos":
    st.title("👥 Directorio de Catequizandos")

    if not st.session_state["admin_logueado"]:
        mostrar_login_admin()
    else:
        resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
        if resp_jovenes.status_code == 200:
            lista = resp_jovenes.json()
            if lista:
                df = pd.DataFrame(lista)
                busqueda = st.text_input("🔍 Buscar por DNI, nombre o apellido:")
                if busqueda:
                    df = df[df.apply(lambda row: busqueda.lower() in row.astype(str).str.lower().to_string(), axis=1)]
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("Aún no hay catequizandos registrados.")
        else:
            st.error("No se pudo cargar el directorio.")

# =========================================================
# SECCIÓN 3: CONTROL DE ASISTENCIAS (3 PESTAÑAS)
# =========================================================
elif pagina == "📋 Control de Asistencias":
    st.title("📋 Control de Asistencias")

    if not st.session_state["admin_logueado"]:
        mostrar_login_admin()
    else:
        tab1, tab2, tab3 = st.tabs(["📖 Catequesis", "⛪ Misas", "🎉 Actividades Parroquiales"])

        def mostrar_tabla_asistencias(tipo_filtro, mostrar_actividad=False):
            resp = requests.get(
                f"{API_URL}/api/v1/asistencias",
                params={"tipo": tipo_filtro},
                timeout=15
            )
            if resp.status_code == 200:
                registros = resp.json()
                if registros:
                    df = pd.DataFrame(registros)
                    if not mostrar_actividad and "Actividad" in df.columns:
                        df = df.drop(columns=["Actividad"])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"No hay asistencias registradas en {tipo_filtro}.")
            else:
                st.error("Error al consultar las asistencias.")

        with tab1:
            mostrar_tabla_asistencias("Catequesis")

        with tab2:
            mostrar_tabla_asistencias("Misa")

        with tab3:
            mostrar_tabla_asistencias("Actividad Parroquial", mostrar_actividad=True)