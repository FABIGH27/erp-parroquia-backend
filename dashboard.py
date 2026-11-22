import streamlit as st
import requests
import pandas as pd
import qrcode
from io import BytesIO

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
        # --- FORMULARIO PARA REGISTRAR NUEVO CATEQUIZANDO ---
        with st.expander("➕ Registrar Nuevo Catequizando"):
            with st.form("form_nuevo_catequizando", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                dni_nuevo = c1.text_input("DNI (8 dígitos)", max_chars=8)
                nombres_nuevo = c2.text_input("Nombres")
                apellidos_nuevo = c3.text_input("Apellidos")
                btn_guardar = st.form_submit_button("Guardar y Generar QR")

                if btn_guardar:
                    if not dni_nuevo or not nombres_nuevo or not apellidos_nuevo:
                        st.warning("Completa todos los campos.")
                    else:
                        resp_crear = requests.post(
                            f"{API_URL}/api/v1/catequizandos",
                            json={
                                "dni": dni_nuevo,
                                "nombres": nombres_nuevo,
                                "apellidos": apellidos_nuevo
                            },
                            timeout=15
                        )
                        if resp_crear.status_code == 200:
                            st.success(f"Registrado correctamente. Token QR: {resp_crear.json()['qr_token']}")
                            st.rerun()
                        else:
                            st.error(resp_crear.json().get("detail", "No se pudo registrar."))

        # --- TABLA DEL DIRECTORIO ---
        resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
        if resp_jovenes.status_code == 200:
            lista = resp_jovenes.json()
            if lista:
                df = pd.DataFrame(lista)
                busqueda = st.text_input("🔍 Buscar por DNI, nombre o apellido:")
                if busqueda:
                    df = df[df.apply(lambda row: busqueda.lower() in row.astype(str).str.lower().to_string(), axis=1)]
                st.dataframe(df, use_container_width=True, hide_index=True)

                # --- GENERADOR Y DESCARGA DE QR ---
                st.divider()
                st.subheader("🎫 Generar y Descargar Código QR")
                opciones = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j for j in lista}
                seleccion = st.selectbox("Selecciona un catequizando:", list(opciones.keys()))
                alumno_sel = opciones[seleccion]

                img_qr = qrcode.make(alumno_sel["QR Token"])
                buffer = BytesIO()
                img_qr.save(buffer, format="PNG")
                bytes_qr = buffer.getvalue()

                col_img, col_btn = st.columns([1, 2])
                with col_img:
                    st.image(bytes_qr, caption=alumno_sel["QR Token"], width=220)
                with col_btn:
                    st.write(f"**Catequizando:** {alumno_sel['Nombres']} {alumno_sel['Apellidos']}")
                    st.write(f"**DNI:** {alumno_sel['DNI']}")
                    st.download_button(
                        label="⬇️ Descargar QR en PNG",
                        data=bytes_qr,
                        file_name=f"QR_{alumno_sel['DNI']}_{alumno_sel['Apellidos']}.png",
                        mime="image/png"
                    )
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