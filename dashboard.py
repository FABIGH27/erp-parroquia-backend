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

if "acceso_temporal" not in st.session_state:
    st.session_state["acceso_temporal"] = False

# =========================================================
# PANTALLA DE INICIO DE SESIÓN GENERAL
# =========================================================
if not st.session_state["admin_logueado"]:
    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    with col_centro:
        st.title("⛪ ERP Parroquial - Confirmación")
        st.subheader("🔒 Inicio de Sesión Administrativo")
        st.caption("Ingresa con tu cuenta de Coordinador, Secretario, Tesorero o Vocal.")

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
st.sidebar.title("⛪ ERP Parroquia")
st.sidebar.success(f"👤 {st.session_state['admin_info']}")

rol_actual = st.session_state.get("admin_rol", "").strip().lower()
es_admin = rol_actual in ["administrador", "admin", "coordinador"]

TODOS_LOS_MODULOS = [
    "📊 Resumen General",
    "👥 Directorio de Catequizandos",
    "📋 Control de Asistencias",
    "💰 Tesorería",
    "📁 Secretaría"
]

PERMISOS_POR_ROL = {
    "administrador": TODOS_LOS_MODULOS + ["🔐 Accesos Temporales"],
    "admin": TODOS_LOS_MODULOS + ["🔐 Accesos Temporales"],
    "coordinador": TODOS_LOS_MODULOS + ["🔐 Accesos Temporales"],
    "vocal": ["📊 Resumen General", "👥 Directorio de Catequizandos", "📋 Control de Asistencias"],
    "tesorero": ["📊 Resumen General", "💰 Tesorería"],
    "tesorera": ["📊 Resumen General", "💰 Tesorería"],
    "secretario": ["📊 Resumen General", "👥 Directorio de Catequizandos", "📁 Secretaría"],
    "secretaria": ["📊 Resumen General", "👥 Directorio de Catequizandos", "📁 Secretaría"],
    "catequista": ["👥 Directorio de Catequizandos", "📋 Control de Asistencias"],
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

    tab_pagos, tab_conceptos = st.tabs(["💵 Registro de Pagos", "⚙️ Catálogo de Conceptos de Pago"])

    resp_conceptos = requests.get(f"{API_URL}/api/v1/tesoreria/conceptos", timeout=15)
    lista_conceptos = resp_conceptos.json() if resp_conceptos.status_code == 200 else []

    with tab_conceptos:
        st.subheader("Catálogo Anual de Conceptos de Pago")
        with st.form("form_nuevo_concepto", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre_conc = c1.text_input("Nombre del Concepto", placeholder="Ej: Inscripción, Retiro, Ceremonia")
            monto_conc = c2.number_input("Monto Sugerido (S/)", min_value=0.0, step=1.0)
            btn_crear_conc = st.form_submit_button("Agregar Concepto")

            if btn_crear_conc:
                if not nombre_conc:
                    st.warning("Ingresa el nombre del concepto.")
                else:
                    r = requests.post(
                        f"{API_URL}/api/v1/tesoreria/conceptos",
                        json={"nombre": nombre_conc.strip(), "monto_sugerido": monto_conc},
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
                with st.form("form_pago", clear_on_submit=True):
                    opciones_j = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j["ID"] for j in lista_jovenes}
                    opciones_c = {
                        f"{c.get('nombre', c.get('nombre_concepto', 'Concepto'))} (S/ {c.get('monto_sugerido', c.get('monto', 0))})": c.get("id_concepto", c.get("id"))
                        for c in lista_conceptos
                    }

                    c_top1, c_top2 = st.columns(2)
                    alumno_sel = c_top1.selectbox("Catequizando", list(opciones_j.keys()))
                    concepto_sel = c_top2.selectbox("Concepto de Pago", list(opciones_c.keys()))

                    c1, c2 = st.columns(2)
                    monto = c1.number_input("Monto Pagado (S/)", min_value=1.0, step=1.0)
                    metodo = c2.selectbox("Método de Pago", ["Efectivo", "Yape", "Plin", "Transferencia"])
                    obs_pago = st.text_input("Observación (opcional)", placeholder="Ej: N° de operación Yape, pago en cuotas...")
                    btn_pago = st.form_submit_button("Registrar Pago")

                    if btn_pago:
                        resp_p = requests.post(
                            f"{API_URL}/api/v1/pagos",
                            json={
                                "id_cateq": opciones_j[alumno_sel],
                                "id_concepto": opciones_c[concepto_sel],
                                "monto": monto,
                                "metodo_pago": metodo,
                                "observaciones": obs_pago.strip() or None
                            },
                            timeout=15
                        )
                        if resp_p.status_code in [200, 201]:
                            st.success("Pago registrado correctamente.")
                            st.rerun()
                        else:
                            st.error(f"Error al registrar pago ({resp_p.status_code}): {resp_p.text}")
            else:
                st.warning("Necesitas tener al menos un catequizando y un concepto de pago en el catálogo.")

        st.subheader("Historial de Pagos")
        resp_pagos = requests.get(f"{API_URL}/api/v1/pagos", timeout=15)
        if resp_pagos.status_code == 200 and resp_pagos.json():
            st.dataframe(pd.DataFrame(resp_pagos.json()), use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay pagos registrados.")

# =========================================================
# SECCIÓN 5: SECRETARÍA
# =========================================================
elif pagina == "📁 Secretaría":
    st.title("📁 Módulo de Secretaría - Expedientes")

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
                        json={"nombre": nombre_doc.strip(), "obligatorio": es_obligatorio},
                        timeout=15
                    )
                    if r.status_code in [200, 201]:
                        st.success("Documento agregado al catálogo.")
                        st.rerun()
                    else:
                        st.error(f"Error ({r.status_code}): {r.text}")

        if lista_docs:
            st.dataframe(pd.DataFrame(lista_docs), use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay documentos requisito registrados para este año.")

    with tab_exp:
        resp_jovenes = requests.get(f"{API_URL}/api/v1/catequizandos", timeout=15)
        lista_jovenes = resp_jovenes.json() if resp_jovenes.status_code == 200 else []

        with st.expander("📝 Registrar / Actualizar Documento de Catequizando", expanded=True):
            if lista_jovenes and lista_docs:
                with st.form("form_expediente", clear_on_submit=True):
                    opciones_j = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j["ID"] for j in lista_jovenes}
                    opciones_d = {
                        d.get("nombre", d.get("nombre_documento", "Documento")): d.get("id_doc", d.get("id"))
                        for d in lista_docs
                    }

                    c1, c2, c3 = st.columns(3)
                    alumno_sel = c1.selectbox("Catequizando", list(opciones_j.keys()))
                    doc_sel = c2.selectbox("Documento Requisito", list(opciones_d.keys()))
                    estado_exp = c3.selectbox("Estado", ["Entregado", "Pendiente", "Observado"])
                    obs_exp = st.text_input("Observación (opcional)", placeholder="Ej: Trajo copia simple, falta original firmada...")
                    btn_exp = st.form_submit_button("Guardar Estado")

                    if btn_exp:
                        resp_e = requests.post(
                            f"{API_URL}/api/v1/expedientes",
                            json={
                                "id_cateq": opciones_j[alumno_sel],
                                "id_doc": opciones_d[doc_sel],
                                "estado": estado_exp,
                                "observaciones": obs_exp.strip() or None
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

        st.subheader("Listado de Expedientes")
        resp_exp = requests.get(f"{API_URL}/api/v1/expedientes", timeout=15)
        if resp_exp.status_code == 200 and resp_exp.json():
            st.dataframe(pd.DataFrame(resp_exp.json()), use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay expedientes registrados.")

# =========================================================
# SECCIÓN 6: ACCESOS TEMPORALES (SOLO ADMIN)
# =========================================================
elif pagina == "🔐 Accesos Temporales":
    st.title("🔐 Gestión de Claves Temporales")
    st.caption("Genera códigos para que otros roles puedan acceder temporalmente a todos los módulos.")

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