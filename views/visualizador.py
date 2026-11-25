import pandas as pd
import requests
import streamlit as st
from utils.api import (
    API_URL,
    api_get,
    TEMAS_CATEQUESIS,
    MISAS_ANUALES,
    ACTIVIDADES_PARROQUIALES,
)
from utils.estilos import mostrar_encabezado_modulo, selector_con_buscador
from utils.reportes import mostrar_botones_exportacion


def mostrar_visualizador():
    mostrar_encabezado_modulo(
        "Visualizador General",
        "Ficha integral de datos, asistencias, pagos y documentos",
        "assets/custodia.jpg",
    )
    st.caption("Consulta en un solo lugar los datos personales, asistencias detalladas, pagos y documentos.")

    lista_j = api_get("/api/v1/catequizandos") or []

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