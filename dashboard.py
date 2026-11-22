import streamlit as st
import requests
import pandas as pd
import qrcode
from io import BytesIO

st.set_page_config(page_title="ERP Parroquia - Confirmación", layout="wide")

API_URL = "https://erp-parroquia-api.onrender.com"

# Estado de sesión global
if "admin_logueado" not in st.session_state:
    st.session_state["admin_logueado"] = False
    st.session_state["admin_info"] = ""
    st.session_state["admin_rol"] = ""

# =========================================================
# PANTALLA DE INICIO DE SESIÓN GENERAL (BLOQUEA TODO HASTA INGRESAR)
# =========================================================
if not st.session_state["admin_logueado"]:
    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    with col_centro:
        st.title("⛪ ERP Parroquial - Confirmación")
        st.subheader("🔒 Inicio de Sesión Administrativo")
        st.caption("Ingresa con tu cuenta de Coordinador, Secretario o Tesorero.")

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
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "Credenciales inválidas."))
                except Exception as e:
                    st.error(f"Error de conexión con la API: {e}")

    st.stop()  # Detiene la carga aquí hasta que inicie sesión

# =========================================================
# MENÚ LATERAL (SOLO VISIBLE TRAS INICIAR SESIÓN)
# =========================================================
st.sidebar.title("⛪ ERP Parroquia")
st.sidebar.success(f"👤 {st.session_state['admin_info']}")

pagina = st.sidebar.radio(
    "Navegación",
    [
        "📊 Resumen General",
        "👥 Directorio de Catequizandos",
        "📋 Control de Asistencias",
        "💰 Tesorería",
        "📁 Secretaría"
    ]
)

st.sidebar.divider()
if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
    st.session_state["admin_logueado"] = False
    st.session_state["admin_info"] = ""
    st.session_state["admin_rol"] = ""
    st.rerun()

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

    resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
    if resp_jovenes.status_code == 200:
        lista = resp_jovenes.json()
        if lista:
            df = pd.DataFrame(lista)
            busqueda = st.text_input("🔍 Buscar por DNI, nombre o apellido:")
            if busqueda:
                df = df[df.apply(lambda row: busqueda.lower() in row.astype(str).str.lower().to_string(), axis=1)]
            st.dataframe(df, use_container_width=True, hide_index=True)

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

# =========================================================
# SECCIÓN 4: TESORERÍA
# =========================================================
elif pagina == "💰 Tesorería":
    st.title("💰 Módulo de Tesorería")

    resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
    lista = resp_jovenes.json() if resp_jovenes.status_code == 200 else []

    with st.expander("➕ Registrar Nuevo Pago / Aporte", expanded=True):
        if lista:
            with st.form("form_pago", clear_on_submit=True):
                opciones = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j["ID"] for j in lista}
                alumno_sel = st.selectbox("Catequizando", list(opciones.keys()))
                c1, c2, c3 = st.columns(3)
                monto = c1.number_input("Monto (S/)", min_value=1.0, step=1.0)
                metodo = c2.selectbox("Método de Pago", ["Efectivo", "Yape", "Plin", "Transferencia"])
                concepto = c3.text_input("Concepto", value="Inscripción / Aporte")
                btn_pago = st.form_submit_button("Registrar Pago")

                if btn_pago:
                    resp_p = requests.post(
                        f"{API_URL}/api/v1/pagos",
                        json={
                            "id_cateq": opciones[alumno_sel],
                            "monto": monto,
                            "metodo_pago": metodo,
                            "concepto": concepto
                        },
                        timeout=15
                    )
                    if resp_p.status_code in [200, 201]:
                        st.success("Pago registrado correctamente.")
                        st.rerun()
                    else:
                        st.error(f"Error al registrar pago ({resp_p.status_code}): {resp_p.text}")
        else:
            st.warning("Registra primero un catequizando en el Directorio.")

    st.subheader("Historial de Pagos")
    resp_pagos = requests.get(f"{API_URL}/api/v1/pagos", timeout=15)
    if resp_pagos.status_code == 200 and resp_pagos.json():
        st.dataframe(pd.DataFrame(resp_pagos.json()), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay pagos registrados o el endpoint GET /api/v1/pagos no está activo.")

# =========================================================
# SECCIÓN 5: SECRETARÍA
# =========================================================
elif pagina == "📁 Secretaría":
    st.title("📁 Módulo de Secretaría - Expedientes")

    resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
    lista = resp_jovenes.json() if resp_jovenes.status_code == 200 else []

    with st.expander("📝 Actualizar Estado de Expediente", expanded=True):
        if lista:
            with st.form("form_expediente", clear_on_submit=True):
                opciones = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j["ID"] for j in lista}
                alumno_sel = st.selectbox("Catequizando", list(opciones.keys()))
                c1, c2 = st.columns(2)
                estado_exp = c1.selectbox("Estado del Expediente", ["Pendiente", "Completo", "Observado"])
                observacion = c2.text_input("Observación / Documentos faltantes", placeholder="Ej: Falta partida de bautismo")
                btn_exp = st.form_submit_button("Guardar Expediente")

                if btn_exp:
                    resp_e = requests.post(
                        f"{API_URL}/api/v1/expedientes",
                        json={
                            "id_cateq": opciones[alumno_sel],
                            "estado": estado_exp,
                            "observaciones": observacion
                        },
                        timeout=15
                    )
                    if resp_e.status_code in [200, 201]:
                        st.success("Expediente actualizado correctamente.")
                        st.rerun()
                    else:
                        st.error(f"Error al guardar expediente ({resp_e.status_code}): {resp_e.text}")
        else:
            st.warning("Registra primero un catequizando en el Directorio.")

    st.subheader("Listado de Expedientes")
    resp_exp = requests.get(f"{API_URL}/api/v1/expedientes", timeout=15)
    if resp_exp.status_code == 200 and resp_exp.json():
        st.dataframe(pd.DataFrame(resp_exp.json()), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay expedientes registrados o el endpoint GET /api/v1/expedientes no está activo.")