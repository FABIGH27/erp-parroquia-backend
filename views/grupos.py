import pandas as pd
import requests
import streamlit as st
from utils.api import (
    API_URL,
    api_get,
    COLEGIOS_PARROQUIA,
    GRUPOS_OPCIONES,
    SALONES_OPCIONES,
    LETRAS_AZ,
)
from utils.estilos import mostrar_encabezado_modulo


def mostrar_grupos():
    mostrar_encabezado_modulo(
        "Asignación de Grupos y Salones",
        "Organiza a los catequizandos por rangos de letras (A–Z) según su apellido o ajústalos manualmente.",
        "assets/paloma.jpg",
    )

    lista_j = api_get("/api/v1/catequizandos") or []

    if not lista_j:
        st.info("Aún no hay catequizandos registrados.")
    else:
        colegio_sel = st.selectbox("1. Selecciona el Colegio:", COLEGIOS_PARROQUIA, key="asig_colegio")
        alumnos_col = [j for j in lista_j if j.get("Colegio") == colegio_sel]
        alumnos_col.sort(key=lambda x: (x.get("Apellidos", "").upper(), x.get("Nombres", "").upper()))

        st.info(f"**{colegio_sel}** tiene actualmente **{len(alumnos_col)}** catequizandos registrados.")

        if alumnos_col:
            tab_az, tab_manual = st.tabs([
                "🔤 Asignación por Rangos de Letras (A–Z)",
                "✏️ Ajuste Manual Rápido (Tabla)"
            ])

            # --- PESTAÑA 1: POR RANGOS DE LETRAS (A-Z) ---
            with tab_az:
                def _letra_inicial(apellido: str) -> str:
                    if not apellido:
                        return "A"
                    c = apellido.strip().upper()[0]
                    reemplazos = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N"}
                    return reemplazos.get(c, c)

                c_modo, c_cant = st.columns(2)
                tipo_asig = c_modo.radio(
                    "¿Qué deseas asignar?",
                    ["Grupo (A, B, C, D)", "Salón (1, 2, 3, 4)"],
                    horizontal=True,
                    key="asig_tipo_az"
                )
                cant_bloques = c_cant.selectbox(
                    "¿En cuántos bloques dividir?",
                    [1, 2, 3, 4],
                    index=0,
                    key="asig_cant_az"
                )

                es_grupo = tipo_asig.startswith("Grupo")
                lista_etiquetas = (
                    ["Grupo A", "Grupo B", "Grupo C", "Grupo D", "Grupo Único"]
                    if es_grupo
                    else ["Salón 1", "Salón 2", "Salón 3", "Salón 4"]
                )

                cortes_default = {
                    1: [("A", "Z")],
                    2: [("A", "M"), ("N", "Z")],
                    3: [("A", "G"), ("H", "P"), ("Q", "Z")],
                    4: [("A", "F"), ("G", "L"), ("M", "R"), ("S", "Z")],
                }[cant_bloques]

                st.markdown("**Define el grupo/salón y el rango de letras (según la inicial del Apellido):**")
                rangos_config = []
                for idx in range(cant_bloques):
                    r1, r2, r3, r4 = st.columns([1.4, 1, 1, 1.4])
                    etiq = r1.selectbox(
                        "Grupo" if es_grupo else "Salón",
                        lista_etiquetas,
                        index=4 if (es_grupo and cant_bloques == 1) else idx,
                        key=f"az_etiq_{es_grupo}_{cant_bloques}_{idx}"
                    )
                    ini_def, fin_def = cortes_default[idx]
                    l_ini = r2.selectbox(
                        "Desde",
                        LETRAS_AZ,
                        index=LETRAS_AZ.index(ini_def),
                        key=f"az_ini_{cant_bloques}_{idx}"
                    )
                    l_fin = r3.selectbox(
                        "Hasta",
                        LETRAS_AZ,
                        index=LETRAS_AZ.index(fin_def),
                        key=f"az_fin_{cant_bloques}_{idx}"
                    )

                    coinciden = [
                        a for a in alumnos_col
                        if l_ini <= _letra_inicial(a.get("Apellidos", "")) <= l_fin
                    ]
                    r4.metric("Jóvenes en rango", len(coinciden))
                    rangos_config.append((etiq, l_ini, l_fin, coinciden))

                if st.button("💾 Aplicar Asignación por Letras", type="primary", key="btn_aplicar_az"):
                    payload = []
                    for etiq, _, _, lista_rango in rangos_config:
                        for a in lista_rango:
                            item = {"id_cateq": a["ID"]}
                            if es_grupo:
                                item["grupo"] = etiq
                            else:
                                item["salon"] = etiq
                            payload.append(item)

                    if not payload:
                        st.warning("No hay jóvenes dentro de los rangos seleccionados.")
                    else:
                        r_mas = requests.put(
                            f"{API_URL}/api/v1/admin/catequizandos/asignar-masivo",
                            json=payload,
                            timeout=30
                        )
                        if r_mas.status_code == 200:
                            st.cache_data.clear()
                            st.success(r_mas.json().get("mensaje", "Asignación aplicada."))
                            st.rerun()
                        else:
                            st.error(f"Error ({r_mas.status_code}): {r_mas.text}")

            # --- PESTAÑA 2: AJUSTE MANUAL TIPO EXCEL ---
            with tab_manual:
                st.caption("Cambia directamente el Grupo o Salón de cualquier joven y presiona Guardar.")
                df_ed = pd.DataFrame([
                    {
                        "ID": a["ID"],
                        "DNI": a["DNI"],
                        "Apellidos": a["Apellidos"],
                        "Nombres": a["Nombres"],
                        "Grupo": a.get("Grupo", "Sin asignar"),
                        "Salón": a.get("Salón", "Sin asignar"),
                    }
                    for a in alumnos_col
                ])

                df_editado = st.data_editor(
                    df_ed,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["ID", "DNI", "Apellidos", "Nombres"],
                    column_config={
                        "Grupo": st.column_config.SelectboxColumn("Grupo", options=GRUPOS_OPCIONES, required=True),
                        "Salón": st.column_config.SelectboxColumn("Salón", options=SALONES_OPCIONES, required=True),
                    },
                    key=f"editor_gs_{colegio_sel}"
                )

                if st.button("💾 Guardar Cambios Manuales", type="primary", key="btn_guardar_gs_manual"):
                    payload_man = [
                        {
                            "id_cateq": int(row["ID"]),
                            "grupo": row["Grupo"],
                            "salon": row["Salón"],
                        }
                        for _, row in df_editado.iterrows()
                    ]
                    r_man = requests.put(
                        f"{API_URL}/api/v1/admin/catequizandos/asignar-masivo",
                        json=payload_man,
                        timeout=30
                    )
                    if r_man.status_code == 200:
                        st.cache_data.clear()
                        st.success(r_man.json().get("mensaje", "Cambios guardados."))
                        st.rerun()
                    else:
                        st.error(f"Error ({r_man.status_code}): {r_man.text}")