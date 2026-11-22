import streamlit as st
import requests
import pandas as pd
import qrcode
from io import BytesIO
from datetime import datetime
from fpdf import FPDF

st.set_page_config(page_title="ERP Parroquia - Confirmación", layout="wide")

API_URL = "https://erp-parroquia-api.onrender.com"

# =========================================================
# FUNCIONES DE EXPORTACIÓN (EXCEL Y PDF)
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
    "administrador": TODOS_LOS_MODULOS + ["🔐 Accesos Temporales", "👤 Gestión de Usuarios"],
    "admin": TODOS_LOS_MODULOS + ["🔐 Accesos Temporales", "👤 Gestión de Usuarios"],
    "coordinador": TODOS_LOS_MODULOS + ["🔐 Accesos Temporales", "👤 Gestión de Usuarios"],
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
            mostrar_botones_exportacion(df, "directorio_catequizandos", "Directorio de Catequizandos")

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

            st.divider()
            with st.expander("✏️ Editar o Eliminar Catequizando"):
                opciones_edit = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j for j in lista}
                sel_edit = st.selectbox(
                    "Selecciona el catequizando a modificar:",
                    list(opciones_edit.keys()),
                    key="sel_edit_cat"
                )
                cat_obj = opciones_edit[sel_edit]

                with st.form("form_editar_catequizando"):
                    c1, c2, c3 = st.columns(3)
                    edit_dni = c1.text_input("DNI", value=cat_obj["DNI"], max_chars=8)
                    edit_nom = c2.text_input("Nombres", value=cat_obj["Nombres"])
                    edit_ape = c3.text_input("Apellidos", value=cat_obj["Apellidos"])
                    if st.form_submit_button("💾 Guardar Cambios"):
                        r_up = requests.put(
                            f"{API_URL}/api/v1/catequizandos/{cat_obj['ID']}",
                            json={"dni": edit_dni, "nombres": edit_nom, "apellidos": edit_ape},
                            timeout=15
                        )
                        if r_up.status_code == 200:
                            st.success("Datos actualizados correctamente.")
                            st.rerun()
                        else:
                            st.error(r_up.json().get("detail", "Error al actualizar."))

                if st.button("🗑️ Eliminar este Catequizando", type="secondary", key="btn_del_cat"):
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
                nombre_slug = tipo_filtro.lower().replace(" ", "_")
                mostrar_botones_exportacion(df, f"asistencias_{nombre_slug}", f"Asistencias - {tipo_filtro}")

                with st.expander("🗑️ Eliminar asistencia duplicada o errónea"):
                    opciones_asis = {
                        f"ID {r['ID']} - {r['Catequizando']} ({r['Fecha y Hora']})": r["ID"]
                        for r in registros
                    }
                    asis_sel = st.selectbox(
                        "Selecciona el registro a eliminar:",
                        list(opciones_asis.keys()),
                        key=f"sel_del_asis_{nombre_slug}"
                    )
                    if st.button("Eliminar Asistencia", key=f"btn_del_asis_{nombre_slug}"):
                        r_del = requests.delete(f"{API_URL}/api/v1/asistencias/{opciones_asis[asis_sel]}", timeout=15)
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
                with st.form("form_pago", clear_on_submit=True):
                    opciones_j = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j["DNI"] for j in lista_jovenes}
                    opciones_c = {
                        f"{c['nombre_conc']} (S/ {c['monto_base']})": c["id_concepto"]
                        for c in lista_conceptos
                    }

                    c_top1, c_top2 = st.columns(2)
                    alumno_sel = c_top1.selectbox("Catequizando", list(opciones_j.keys()))
                    concepto_sel = c_top2.selectbox("Concepto de Pago", list(opciones_c.keys()))

                    c1, c2 = st.columns(2)
                    monto = c1.number_input("Monto Pagado (S/)", min_value=1.0, step=1.0)
                    metodo = c2.selectbox("Método de Pago", ["Efectivo", "Yape", "Transferencia"])
                    btn_pago = st.form_submit_button("Registrar Pago")

                    if btn_pago:
                        resp_p = requests.post(
                            f"{API_URL}/api/v1/tesoreria/pagos",
                            json={
                                "dni_catequizando": opciones_j[alumno_sel],
                                "id_concepto": opciones_c[concepto_sel],
                                "monto": monto,
                                "metodo_pago": metodo,
                                "id_usuario": 1
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
        resp_pagos = requests.get(f"{API_URL}/api/v1/tesoreria/pagos", timeout=15)
        if resp_pagos.status_code == 200:
            data_pagos = resp_pagos.json()
            lista_pagos = data_pagos.get("pagos", [])
            if lista_pagos:
                st.metric("Total Recaudado", f"S/ {data_pagos.get('total_recaudado', 0):.2f}")
                df_pagos = pd.DataFrame(lista_pagos)
                st.dataframe(df_pagos, use_container_width=True, hide_index=True)
                mostrar_botones_exportacion(df_pagos, "reporte_pagos", "Reporte de Tesoreria - Pagos")

                with st.expander("🗑️ Anular / Eliminar un Pago"):
                    opciones_pagos = {
                        f"ID {p['id_pago']} - {p['alumno']} | {p['concepto']} (S/ {p['monto']})": p["id_pago"]
                        for p in lista_pagos
                    }
                    pago_sel = st.selectbox(
                        "Selecciona el pago a anular:",
                        list(opciones_pagos.keys()),
                        key="sel_del_pago"
                    )
                    if st.button("Anular Pago Seleccionado", key="btn_del_pago"):
                        r_del = requests.delete(
                            f"{API_URL}/api/v1/tesoreria/pagos/{opciones_pagos[pago_sel]}",
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
                doc_del_sel = st.selectbox(
                    "Selecciona el documento a eliminar:",
                    list(opciones_del_doc.keys()),
                    key="sel_del_doc"
                )
                if st.button("Eliminar Documento", key="btn_del_doc"):
                    r_del = requests.delete(
                        f"{API_URL}/api/v1/secretaria/documentos/{opciones_del_doc[doc_del_sel]}",
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
                                "id_usuario": 1
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
            opciones_consulta = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j["DNI"] for j in lista_jovenes}
            alumno_consulta = st.selectbox(
                "Selecciona un catequizando para ver sus documentos:",
                list(opciones_consulta.keys())
            )
            dni_consulta = opciones_consulta[alumno_consulta]

            resp_exp = requests.get(f"{API_URL}/api/v1/secretaria/expedientes/{dni_consulta}", timeout=15)
            if resp_exp.status_code == 200:
                docs_alumno = resp_exp.json().get("documentos", [])
                if docs_alumno:
                    df_exp = pd.DataFrame(docs_alumno)
                    st.dataframe(df_exp, use_container_width=True, hide_index=True)
                    mostrar_botones_exportacion(df_exp, f"expediente_{dni_consulta}", f"Expediente - {alumno_consulta}")

                    with st.expander("🗑️ Eliminar Registro de Expediente"):
                        opciones_del_exp = {
                            f"ID {d['id_exp']} - {d['documento']} ({d['estado']})": d["id_exp"]
                            for d in docs_alumno if "id_exp" in d
                        }
                        if opciones_del_exp:
                            exp_del_sel = st.selectbox(
                                "Selecciona el registro a eliminar:",
                                list(opciones_del_exp.keys()),
                                key="sel_del_exp"
                            )
                            if st.button("Eliminar Registro", key="btn_del_exp"):
                                r_del = requests.delete(
                                    f"{API_URL}/api/v1/secretaria/expedientes/{opciones_del_exp[exp_del_sel]}",
                                    timeout=15
                                )
                                if r_del.status_code == 200:
                                    st.success("Registro de expediente eliminado.")
                                    st.rerun()
                                else:
                                    st.error("No se pudo eliminar el registro.")
                else:
                    st.info("Este catequizando aún no tiene documentos registrados.")
            else:
                st.error("No se pudo consultar el expediente.")

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
        u_eliminar = st.selectbox("Seleccionar usuario para eliminar:", list(opciones_del.keys()))
        if st.button("🗑️ Eliminar Usuario Seleccionado"):
            r_del = requests.delete(
                f"{API_URL}/api/v1/admin/usuarios/{opciones_del[u_eliminar]}",
                timeout=15
            )
            if r_del.status_code == 200:
                st.success("Usuario eliminado.")
                st.rerun()
            else:
                st.error(f"No se pudo eliminar: {r_del.text}")
    else:
        st.info("No hay usuarios registrados.")