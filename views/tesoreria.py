import pandas as pd
import requests
import streamlit as st
from utils.api import API_URL, api_get, COLEGIOS_PARROQUIA, GRUPOS_OPCIONES
from utils.estilos import mostrar_encabezado_modulo, selector_con_buscador
from utils.reportes import mostrar_botones_exportacion


def mostrar_tesoreria():
    mostrar_encabezado_modulo(
        "Módulo de Tesorería",
        "Control de aportes, conceptos y recaudación",
        "assets/corazon.jpg",
    )

    tab_pagos, tab_conceptos = st.tabs(["💵 Registro de Pagos", "⚙️ Catálogo de Conceptos de Pago"])

    lista_conceptos = api_get("/api/v1/tesoreria/conceptos") or []

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
                        st.cache_data.clear()
                        st.success("Concepto agregado al catálogo.")
                        st.rerun()
                    else:
                        st.error(f"Error ({r.status_code}): {r.text}")

        if lista_conceptos:
            st.dataframe(pd.DataFrame(lista_conceptos), use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay conceptos de pago registrados para este año.")

    with tab_pagos:
        lista_jovenes = api_get("/api/v1/catequizandos") or []

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
                                st.cache_data.clear()
                                st.success(
                                    f"Pago registrado (S/ {float(conc_obj['monto_base']):.2f} | Boleta: {codigo_boleta.strip()})."
                                )
                                st.rerun()
                            else:
                                st.error(f"Error al registrar pago ({resp_p.status_code}): {resp_p.text}")
            else:
                st.warning("Necesitas tener al menos un catequizando y un concepto de pago en el catálogo.")

        st.subheader("Historial de Pagos")
        data_pagos = api_get("/api/v1/tesoreria/pagos")
        if data_pagos is not None:
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
                            st.cache_data.clear()
                            st.success("Pago anulado correctamente.")
                            st.rerun()
                        else:
                            st.error("No se pudo anular el pago.")
            else:
                st.info("Aún no hay pagos registrados.")
        else:
            st.error("No se pudo cargar el historial de pagos.")