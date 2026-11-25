import altair as alt
import pandas as pd
import streamlit as st
from utils.api import ahora_peru, api_get, COLEGIOS_PARROQUIA, GRUPOS_OPCIONES
from utils.estilos import _img_b64
from utils.reportes import mostrar_botones_exportacion


def mostrar_resumen():
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
        res = api_get("/api/v1/dashboard/resumen")
        if res is not None:
            datos = res
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
                all_asis = api_get("/api/v1/asistencias") or []
                total_asis_mostrar = sum(
                    1 for a in all_asis
                    if str(a.get("Fecha y Hora", "")).startswith(fecha_iso)
                )
                etiqueta_asis = f"Asistencias ({'Hoy' if modo_asis == 'Hoy' else fecha_obj.strftime('%d/%m/%Y')})"

            col1, col2, col3 = st.columns(3)
            col1.metric("Catequizandos Registrados", kpis["total_catequizandos"])
            col2.metric(etiqueta_asis, total_asis_mostrar)
            col3.metric("Total Recaudado (S/)", f"S/ {kpis['total_recaudado']:.2f}")

            st.divider()
            alertas = api_get("/api/v1/dashboard/alertas")
            deudores = (alertas or {}).get("deudores", [])
            docs_pend = (alertas or {}).get("documentos_pendientes", [])
            asis_res = (alertas or {}).get("asistencias_resumen", [])

            lista_conceptos = [c["nombre_conc"] for c in (api_get("/api/v1/tesoreria/conceptos") or [])]
            lista_docs = [d["nombre_doc"] for d in (api_get("/api/v1/secretaria/documentos") or [])]

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

            if alertas is not None:
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