import pandas as pd
import requests
import streamlit as st
from utils.api import (
    API_URL,
    ahora_peru,
    api_get,
    COLEGIOS_PARROQUIA,
    TEMAS_CATEQUESIS,
    MISAS_ANUALES,
    ACTIVIDADES_PARROQUIALES,
)
from utils.estilos import mostrar_encabezado_modulo, selector_con_buscador
from utils.reportes import mostrar_botones_exportacion


def mostrar_asistencias():
    mostrar_encabezado_modulo(
        "Control de Asistencias",
        "Seguimiento de los temas, misas y actividades parroquiales",
        "assets/llama.jpg",
    )

    tab1, tab2, tab3 = st.tabs(["📖 Catequesis (26 Temas)", "⛪ Misas (30 Misas)", "🎉 Actividades Parroquiales"])

    @st.fragment
    def mostrar_tabla_asistencias(tipo_filtro, etiqueta_detalle, opciones_detalle):
        registros = api_get("/api/v1/asistencias", {"tipo": tipo_filtro})
        if registros is not None:
            if registros:
                nombre_slug = tipo_filtro.lower().replace(" ", "_")
                df = pd.DataFrame(registros)

                # Renombrar columna 'Actividad' a 'Tema', 'Misa' o 'Actividad'
                if "Actividad" in df.columns:
                    df = df.rename(columns={"Actividad": etiqueta_detalle})

                # Filtros en fila: Buscador + Tema/Misa/Actividad + Colegio
                f1, f2, f3 = st.columns([2, 1.2, 1.2])
                busq_asis = f1.text_input(
                    "🔍 Buscar por DNI, nombre o fecha:",
                    key=f"busq_tabla_asis_{nombre_slug}"
                )
                filtro_det = f2.selectbox(
                    f"Filtrar por {etiqueta_detalle}:",
                    ["Todos"] + opciones_detalle,
                    key=f"filt_det_{nombre_slug}"
                )
                filtro_col = f3.selectbox(
                    "Filtrar por Colegio:",
                    ["Todos"] + COLEGIOS_PARROQUIA,
                    key=f"filt_col_{nombre_slug}"
                )

                # Fila 2 de filtros: Fecha (General / Hoy / Por fecha)
                fd1, fd2, _ = st.columns([1.2, 1.2, 2])
                modo_fecha_tab = fd1.selectbox(
                    "Filtrar por Fecha:",
                    ["General", "Hoy", "Por fecha"],
                    key=f"modo_fecha_{nombre_slug}"
                )
                fecha_tab_sel = None
                if modo_fecha_tab == "Por fecha":
                    fecha_tab_sel = fd2.date_input(
                        "Selecciona la fecha:",
                        value=ahora_peru().date(),
                        key=f"fecha_sel_{nombre_slug}"
                    )

                df_filtrado = df.copy()
                if busq_asis.strip():
                    q = busq_asis.strip().lower()
                    df_filtrado = df_filtrado[
                        df_filtrado.apply(lambda row: q in row.astype(str).str.lower().to_string(), axis=1)
                    ]
                if filtro_det != "Todos" and etiqueta_detalle in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado[etiqueta_detalle] == filtro_det]
                if filtro_col != "Todos" and "Colegio" in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado["Colegio"] == filtro_col]
                if modo_fecha_tab in ("Hoy", "Por fecha") and "Fecha y Hora" in df_filtrado.columns:
                    f_obj = ahora_peru().date() if modo_fecha_tab == "Hoy" else fecha_tab_sel
                    f_iso = f_obj.strftime("%Y-%m-%d")
                    df_filtrado = df_filtrado[
                        df_filtrado["Fecha y Hora"].astype(str).str.startswith(f_iso)
                    ]

                st.caption(f"Mostrando **{len(df_filtrado)}** de **{len(df)}** asistencias.")
                st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
                mostrar_botones_exportacion(df_filtrado, f"asistencias_{nombre_slug}", f"Asistencias - {tipo_filtro}")

                with st.expander("🗑️ Eliminar asistencia duplicada o errónea"):
                    opciones_asis = {
                        f"ID {r['ID']} - {r['Catequizando']} (DNI: {r['DNI']}) | {r.get('Actividad', '-')} | {r['Fecha y Hora']}": r["ID"]
                        for r in registros
                    }
                    id_asis_sel = selector_con_buscador(
                        "Asistencia a eliminar",
                        opciones_asis,
                        f"del_asis_{nombre_slug}",
                        placeholder="Buscar por DNI, nombre, ID o fecha..."
                    )
                    if id_asis_sel and st.button("Eliminar Asistencia", key=f"btn_del_asis_{nombre_slug}"):
                        r_del = requests.delete(f"{API_URL}/api/v1/asistencias/{id_asis_sel}", timeout=15)
                        if r_del.status_code == 200:
                            st.cache_data.clear()
                            st.success("Asistencia eliminada.")
                            st.rerun()
                        else:
                            st.error("No se pudo eliminar la asistencia.")
            else:
                st.info(f"No hay asistencias registradas en {tipo_filtro}.")
        else:
            st.error("Error al consultar las asistencias.")

    with tab1:
        mostrar_tabla_asistencias("Catequesis", "Tema", TEMAS_CATEQUESIS)
    with tab2:
        mostrar_tabla_asistencias("Misa", "Misa", MISAS_ANUALES)
    with tab3:
        mostrar_tabla_asistencias("Actividad Parroquial", "Actividad", ACTIVIDADES_PARROQUIALES)