import streamlit as st
import requests
import pandas as pd

API_URL = "https://erp-parroquia-api.onrender.com"

st.set_page_config(page_title="ERP Parroquia - Panel Administrativo", layout="wide")
st.title("⛪ ERP Parroquia — Dashboard Administrativo")

# Menú lateral
menu = st.sidebar.radio(
    "Navegación",
    ["📊 Resumen General", "💰 Tesorería", "📁 Secretaría"]
)

# =========================================================
# 1. RESUMEN GENERAL (KPIs)
# =========================================================
if menu == "📊 Resumen General":
    st.subheader("Métricas en Tiempo Real")
    try:
        res = requests.get(f"{API_URL}/api/v1/dashboard/resumen")
        if res.status_code == 200:
            data = res.json()
            kpis = data["kpis"]

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Catequizandos", kpis["total_catequizandos"])
            col2.metric("Asistencias Registradas", kpis["total_asistencias_registradas"])
            col3.metric("Total Recaudado (S/)", f"S/ {kpis['total_recaudado']:.2f}")

            st.divider()
            c_izq, c_der = st.columns(2)

            with c_izq:
                st.markdown("**Recaudación por Método de Pago**")
                if data["recaudacion_por_metodo"]:
                    df_metodos = pd.DataFrame(
                        list(data["recaudacion_por_metodo"].items()),
                        columns=["Método", "Monto (S/)"]
                    ).set_index("Método")
                    st.bar_chart(df_metodos)
                else:
                    st.info("Aún no hay pagos registrados.")

            with c_der:
                st.markdown("**Estado de Expedientes**")
                if data["estado_expedientes"]:
                    df_exp = pd.DataFrame(
                        list(data["estado_expedientes"].items()),
                        columns=["Estado", "Cantidad"]
                    ).set_index("Estado")
                    st.bar_chart(df_exp)
                else:
                    st.info("Aún no hay expedientes registrados.")
        else:
            st.error("No se pudo obtener el resumen del servidor.")
    except Exception as e:
        st.error(f"Error de conexión con FastAPI: {e}")

# =========================================================
# 2. TESORERÍA
# =========================================================
elif menu == "💰 Tesorería":
    st.subheader("Gestión de Pagos y Caja")

    col_form, col_tabla = st.columns([1, 2])

    with col_form:
        st.markdown("**Registrar Nuevo Cobro**")
        # Cargar conceptos disponibles
        conceptos_res = requests.get(f"{API_URL}/api/v1/tesoreria/conceptos")
        conceptos = conceptos_res.json() if conceptos_res.status_code == 200 else []

        if conceptos:
            opciones_conc = {f"{c['nombre_conc']} (S/ {c['monto_base']})": c["id_concepto"] for c in conceptos}
            with st.form("form_pago"):
                dni = st.text_input("DNI del Catequizando", max_chars=8)
                conc_sel = st.selectbox("Concepto de Pago", list(opciones_conc.keys()))
                metodo = st.selectbox("Método de Pago", ["Efectivo", "Yape", "Transferencia"])
                enviar = st.form_submit_button("Registrar Pago")

                if enviar:
                    payload = {
                        "dni_catequizando": dni,
                        "id_concepto": opciones_conc[conc_sel],
                        "metodo_pago": metodo,
                        "id_usuario": 1
                    }
                    r = requests.post(f"{API_URL}/api/v1/tesoreria/pagos", json=payload)
                    if r.status_code == 200:
                        st.success(f"Pago registrado para {r.json()['alumno']}")
                    else:
                        st.error(r.json().get("detail", "Error al registrar pago"))
        else:
            st.warning("Primero crea al menos un concepto de pago en Swagger.")

    with col_tabla:
        st.markdown("**Historial de Pagos**")
        pagos_res = requests.get(f"{API_URL}/api/v1/tesoreria/pagos")
        if pagos_res.status_code == 200:
            datos_pagos = pagos_res.json()
            st.metric("Caja Acumulada", f"S/ {datos_pagos['total_recaudado']:.2f}")
            if datos_pagos["pagos"]:
                st.dataframe(pd.DataFrame(datos_pagos["pagos"]), use_container_width=True)
            else:
                st.info("Sin pagos registrados.")

# =========================================================
# 3. SECRETARÍA
# =========================================================
elif menu == "📁 Secretaría":
    st.subheader("Control Documental y Expedientes")

    col_reg, col_cons = st.columns(2)

    with col_reg:
        st.markdown("**Actualizar Estado de Documento**")
        docs_res = requests.get(f"{API_URL}/api/v1/secretaria/documentos")
        docs = docs_res.json() if docs_res.status_code == 200 else []

        if docs:
            opciones_doc = {d["nombre_doc"]: d["id_doc"] for d in docs}
            with st.form("form_expediente"):
                dni_exp = st.text_input("DNI del Catequizando", max_chars=8)
                doc_sel = st.selectbox("Documento Requisito", list(opciones_doc.keys()))
                estado_sel = st.selectbox("Estado", ["Entregado", "Pendiente", "Observado"])
                guardar = st.form_submit_button("Guardar en Expediente")

                if guardar:
                    payload = {
                        "dni_catequizando": dni_exp,
                        "id_doc": opciones_doc[doc_sel],
                        "estado": estado_sel,
                        "id_usuario": 1
                    }
                    r = requests.post(f"{API_URL}/api/v1/secretaria/expedientes", json=payload)
                    if r.status_code == 200:
                        st.success(r.json()["mensaje"])
                    else:
                        st.error(r.json().get("detail", "Error al actualizar expediente"))
        else:
            st.warning("Primero crea documentos requisito en Swagger.")

    with col_cons:
        st.markdown("**Consultar Expediente por DNI**")
        dni_buscar = st.text_input("Ingresa DNI para consultar", max_chars=8)
        if st.button("Buscar Expediente") and dni_buscar:
            r = requests.get(f"{API_URL}/api/v1/secretaria/expedientes/{dni_buscar}")
            if r.status_code == 200:
                info = r.json()
                st.write(f"**Alumno:** {info['alumno']}")
                if info["documentos"]:
                    st.dataframe(pd.DataFrame(info["documentos"]), use_container_width=True)
                else:
                    st.info("Este alumno aún no tiene documentos registrados.")
            else:
                st.error(r.json().get("detail", "No encontrado"))

st.divider()
st.subheader("👥 Directorio de Catequizandos (Acceso Restringido)")

# Estado de sesión para recordar si ya inició sesión
if "admin_logueado" not in st.session_state:
    st.session_state["admin_logueado"] = False
    st.session_state["admin_info"] = ""

if not st.session_state["admin_logueado"]:
    with st.form("login_admin_form"):
        st.info("Inicia sesión con credenciales de Coordinador, Secretario o Tesorero.")
        dni_input = st.text_input("DNI de Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        btn_ingresar = st.form_submit_button("Ingresar")

        if btn_ingresar:
            resp = requests.post(
                f"{API_URL}/api/v1/admin/login",
                json={"dni": dni_input, "password": pass_input}
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["admin_logueado"] = True
                st.session_state["admin_info"] = f"{data['usuario']} ({data['rol']})"
                st.rerun()
            else:
                st.error(resp.json().get("detail", "Credenciales inválidas."))
else:
    col1, col2 = st.columns([4, 1])
    col1.success(f"Sesión activa: **{st.session_state['admin_info']}**")
    if col2.button("Cerrar sesión"):
        st.session_state["admin_logueado"] = False
        st.rerun()

    # Cargar y mostrar la tabla de jóvenes
    resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos")
    if resp_jovenes.status_code == 200:
        lista = resp_jovenes.json()
        if lista:
            df = pd.DataFrame(lista)
            busqueda = st.text_input("🔍 Buscar por DNI, nombre o apellido:")
            if busqueda:
                df = df[df.apply(lambda row: busqueda.lower() in row.astype(str).str.lower().to_string(), axis=1)]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("Aún no hay catequizandos registrados en la base de datos.")
    else:
        st.error("No se pudo cargar la lista de catequizandos.")