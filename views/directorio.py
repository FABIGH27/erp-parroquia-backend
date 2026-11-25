from io import BytesIO
import pandas as pd
import qrcode
import requests
import streamlit as st
from utils.api import (
    API_URL,
    ahora_peru,
    api_get,
    COLEGIOS_PARROQUIA,
    ESTADOS_BAUTISMO,
    GRUPOS_OPCIONES,
    SALONES_OPCIONES,
)
from utils.estilos import mostrar_encabezado_modulo, selector_con_buscador
from utils.reportes import (
    mostrar_botones_exportacion,
    generar_carnet_individual_pdf,
    generar_carnets_bloque_pdf,
)


def mostrar_directorio():
    mostrar_encabezado_modulo(
        "Directorio de Catequizandos",
        "Registro, carnets QR y gestión de jóvenes",
        "assets/san_francisco.jpg",
    )

    with st.expander("➕ Registrar Nuevo Catequizando"):
        with st.form("form_nuevo_catequizando", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            dni_nuevo = c1.text_input("DNI del Joven (8 dígitos) *", max_chars=8)
            nombres_nuevo = c2.text_input("Nombres *")
            apellidos_nuevo = c3.text_input("Apellidos *")

            c4, c5, c6 = st.columns(3)
            colegio_nuevo = c4.selectbox("Colegio", COLEGIOS_PARROQUIA)
            bautismo_nuevo = c5.selectbox("Bautismo", ESTADOS_BAUTISMO)
            cel_joven_nuevo = c6.text_input("Celular del Joven", max_chars=15, placeholder="Ej: 987654321")

            st.markdown("**Contactos de Apoderados (hasta 2)**")
            a1, a2 = st.columns(2)
            cel_ap1_nuevo = a1.text_input("Celular Apoderado 1", max_chars=15, placeholder="Ej: 912345678")
            par_ap1_nuevo = a2.text_input("¿De quién es? (Apoderado 1)", placeholder="Ej: Mamá - María")

            a3, a4 = st.columns(2)
            cel_ap2_nuevo = a3.text_input("Celular Apoderado 2 (Opcional)", max_chars=15)
            par_ap2_nuevo = a4.text_input("¿De quién es? (Apoderado 2 - Opcional)", placeholder="Ej: Papá - Juan")

            btn_guardar = st.form_submit_button("Guardar y Generar QR", type="primary")

            if btn_guardar:
                if not dni_nuevo.strip() or not nombres_nuevo.strip() or not apellidos_nuevo.strip():
                    st.warning("Completa al menos DNI, Nombres y Apellidos.")
                else:
                    resp_crear = requests.post(
                        f"{API_URL}/api/v1/catequizandos",
                        json={
                            "dni": dni_nuevo.strip(),
                            "nombres": nombres_nuevo.strip(),
                            "apellidos": apellidos_nuevo.strip(),
                            "colegio": colegio_nuevo,
                            "estado_bautismo": bautismo_nuevo,
                            "celular_joven": cel_joven_nuevo.strip() or None,
                            "celular_apoderado_1": cel_ap1_nuevo.strip() or None,
                            "parentesco_apoderado_1": par_ap1_nuevo.strip() or None,
                            "celular_apoderado_2": cel_ap2_nuevo.strip() or None,
                            "parentesco_apoderado_2": par_ap2_nuevo.strip() or None,
                        },
                        timeout=15
                    )
                    if resp_crear.status_code in (200, 201):
                        st.cache_data.clear()
                        st.success(f"Registrado correctamente. Token QR: {resp_crear.json().get('qr_token', '')}")
                        st.rerun()
                    else:
                        try:
                            msg = resp_crear.json().get("detail", resp_crear.text)
                        except Exception:
                            msg = resp_crear.text
                        st.error(f"Error ({resp_crear.status_code}): {msg}")

    lista = api_get("/api/v1/catequizandos")
    if lista is not None:
        if lista:
            df = pd.DataFrame(lista)

            # Filtros rápidos (buscador + colegio + bautismo)
            @st.fragment
            def _tabla_directorio(df_base):
                f1, f2, f3 = st.columns([2, 1.2, 1.2])
                busqueda = f1.text_input("🔍 Buscar por DNI, nombre, apellido o celular:", key="busq_cat_dir")
                filtro_colegio = f2.selectbox("Colegio", ["Todos"] + COLEGIOS_PARROQUIA, key="filt_col_dir")
                filtro_bautismo = f3.selectbox("Bautismo", ["Todos"] + ESTADOS_BAUTISMO, key="filt_baut_dir")

                df_filtrado = df_base.copy()
                if busqueda.strip():
                    q = busqueda.strip().lower()
                    df_filtrado = df_filtrado[
                        df_filtrado.apply(lambda row: q in row.astype(str).str.lower().to_string(), axis=1)
                    ]
                if filtro_colegio != "Todos" and "Colegio" in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado["Colegio"] == filtro_colegio]
                if filtro_bautismo != "Todos" and "Bautismo" in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado["Bautismo"] == filtro_bautismo]

                cols_visibles = [c for c in df_filtrado.columns if not c.endswith("_raw")]
                df_mostrar = df_filtrado[cols_visibles]

                st.caption(f"Mostrando **{len(df_mostrar)}** de **{len(df_base)}** catequizandos.")
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
                mostrar_botones_exportacion(df_mostrar, "directorio_catequizandos", "Directorio de Catequizandos")
                st.session_state["dnis_directorio_filtrados"] = set(df_mostrar["DNI"].tolist())

            _tabla_directorio(df)

            st.divider()
            st.subheader("🎫 Carnet QR Individual")
            opciones_qr = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j for j in lista}
            alumno_sel = selector_con_buscador("Catequizando para QR", opciones_qr, "qr_cat")

            if alumno_sel:
                img_qr = qrcode.make(alumno_sel["QR Token"])
                buffer = BytesIO()
                img_qr.save(buffer, format="PNG")
                bytes_qr = buffer.getvalue()

                col_img, col_btn = st.columns([1, 2])
                with col_img:
                    st.image(bytes_qr, caption=alumno_sel["QR Token"], width=200)
                with col_btn:
                    st.write(f"**Catequizando:** {alumno_sel['Nombres']} {alumno_sel['Apellidos']}")
                    st.write(f"**DNI:** {alumno_sel['DNI']}")
                    st.write(f"**Colegio:** {alumno_sel.get('Colegio', 'Sin asignar')}")
                    st.write(f"**Bautismo:** {alumno_sel.get('Bautismo', 'Bautizado')}")
                    b1, b2 = st.columns(2)
                    with b1:
                        st.download_button(
                            label="🪪 Descargar Carnet PDF (Pequeño)",
                            data=generar_carnet_individual_pdf(alumno_sel),
                            file_name=f"Carnet_{alumno_sel['DNI']}_{alumno_sel['Apellidos']}.pdf",
                            mime="application/pdf",
                            key=f"pdf_carnet_{alumno_sel['DNI']}"
                        )
                    with b2:
                        st.download_button(
                            label="⬇️ Solo imagen QR (PNG)",
                            data=bytes_qr,
                            file_name=f"QR_{alumno_sel['DNI']}_{alumno_sel['Apellidos']}.png",
                            mime="image/png",
                            key=f"png_qr_{alumno_sel['DNI']}"
                        )

            st.divider()
            with st.expander("🖨️ Impresión de Carnets QR en Bloque (Hoja A4 - 10 por página)"):
                modo_bloque = st.radio(
                    "¿Qué carnets deseas generar?",
                    [
                        "Por Colegio, Grupo y/o Salón",
                        "Todos los catequizandos filtrados en la tabla superior",
                        "Seleccionar catequizandos específicos",
                    ],
                    horizontal=True,
                    key="modo_bloque_qr"
                )

                alumnos_a_imprimir = []
                etiqueta_archivo = "Bloque"

                if modo_bloque == "Por Colegio, Grupo y/o Salón":
                    b1, b2, b3 = st.columns(3)
                    col_qr = b1.selectbox("Colegio:", ["Todos"] + COLEGIOS_PARROQUIA, key="qr_bloque_col")
                    grp_qr = b2.selectbox("Grupo:", ["Todos"] + GRUPOS_OPCIONES, key="qr_bloque_grp")
                    sal_qr = b3.selectbox("Salón:", ["Todos"] + SALONES_OPCIONES, key="qr_bloque_sal")

                    alumnos_a_imprimir = lista.copy()
                    partes_nombre = []
                    if col_qr != "Todos":
                        alumnos_a_imprimir = [j for j in alumnos_a_imprimir if j.get("Colegio") == col_qr]
                        partes_nombre.append(col_qr.replace(" ", "_"))
                    if grp_qr != "Todos":
                        alumnos_a_imprimir = [j for j in alumnos_a_imprimir if j.get("Grupo", "Sin asignar") == grp_qr]
                        partes_nombre.append(grp_qr.replace(" ", "_"))
                    if sal_qr != "Todos":
                        alumnos_a_imprimir = [j for j in alumnos_a_imprimir if j.get("Salón", "Sin asignar") == sal_qr]
                        partes_nombre.append(sal_qr.replace(" ", "_"))

                    if partes_nombre:
                        etiqueta_archivo = "_".join(partes_nombre)

                elif modo_bloque == "Todos los catequizandos filtrados en la tabla superior":
                    dnis_filtrados = st.session_state.get("dnis_directorio_filtrados", set(df["DNI"].tolist()))
                    alumnos_a_imprimir = [j for j in lista if j["DNI"] in dnis_filtrados]
                    etiqueta_archivo = "Filtrados"

                else:
                    opciones_multi = {
                        f"{j['Apellidos']}, {j['Nombres']} (DNI: {j['DNI']} - {j.get('Colegio', 'Sin asignar')})": j
                        for j in lista
                    }
                    seleccionados = st.multiselect(
                        "Elige los catequizandos (puedes escribir para buscar):",
                        list(opciones_multi.keys()),
                        key="multi_qr_bloque"
                    )
                    alumnos_a_imprimir = [opciones_multi[s] for s in seleccionados]
                    etiqueta_archivo = "Seleccion"

                # Ordenar alfabéticamente por Apellidos y Nombres
                alumnos_a_imprimir.sort(
                    key=lambda x: (x.get("Apellidos", "").upper(), x.get("Nombres", "").upper())
                )

                if alumnos_a_imprimir:
                    st.caption(
                        f"Se generarán **{len(alumnos_a_imprimir)}** carnets ordenados alfabéticamente "
                        f"({(len(alumnos_a_imprimir) + 9) // 10} hoja(s) A4)."
                    )
                    if st.button("⚙️ Preparar PDF en Bloque", key="btn_prep_bloque", type="primary"):
                        with st.spinner("Generando carnets..."):
                            pdf_bloque = generar_carnets_bloque_pdf(alumnos_a_imprimir)
                        st.download_button(
                            label="📄 Descargar PDF de Carnets A4",
                            data=pdf_bloque,
                            file_name=f"Carnets_QR_{etiqueta_archivo}_{ahora_peru().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            key="btn_dl_bloque"
                        )
                else:
                    st.info("No hay catequizandos que coincidan con los filtros seleccionados.")

            st.divider()
            with st.expander("✏️ Editar o Eliminar Catequizando"):
                opciones_edit = {f"ID {j['ID']} - {j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j for j in lista}
                cat_obj = selector_con_buscador("Catequizando a modificar", opciones_edit, "edit_cat")

                if cat_obj:
                    col_actual = cat_obj.get("Colegio", "Particulares")
                    idx_col = COLEGIOS_PARROQUIA.index(col_actual) if col_actual in COLEGIOS_PARROQUIA else len(COLEGIOS_PARROQUIA) - 1

                    baut_actual = cat_obj.get("Bautismo", "Bautizado")
                    idx_baut = ESTADOS_BAUTISMO.index(baut_actual) if baut_actual in ESTADOS_BAUTISMO else 0

                    with st.form(f"form_editar_cat_{cat_obj['ID']}"):
                        c1, c2, c3 = st.columns(3)
                        edit_dni = c1.text_input("DNI del Joven *", value=cat_obj["DNI"], max_chars=8)
                        edit_nom = c2.text_input("Nombres *", value=cat_obj["Nombres"])
                        edit_ape = c3.text_input("Apellidos *", value=cat_obj["Apellidos"])

                        c4, c5, c6 = st.columns(3)
                        edit_col = c4.selectbox("Colegio", COLEGIOS_PARROQUIA, index=idx_col)
                        edit_baut = c5.selectbox("Bautismo", ESTADOS_BAUTISMO, index=idx_baut)
                        edit_cel_j = c6.text_input("Celular del Joven", value=cat_obj.get("celular_joven_raw", ""), max_chars=15)

                        st.markdown("**Contactos de Apoderados (hasta 2)**")
                        ea1, ea2 = st.columns(2)
                        edit_cel_ap1 = ea1.text_input("Celular Apoderado 1", value=cat_obj.get("celular_apoderado_1_raw", ""), max_chars=15)
                        edit_par_ap1 = ea2.text_input("¿De quién es? (Apoderado 1)", value=cat_obj.get("parentesco_apoderado_1_raw", ""))

                        ea3, ea4 = st.columns(2)
                        edit_cel_ap2 = ea3.text_input("Celular Apoderado 2 (Opcional)", value=cat_obj.get("celular_apoderado_2_raw", ""), max_chars=15)
                        edit_par_ap2 = ea4.text_input("¿De quién es? (Apoderado 2 - Opcional)", value=cat_obj.get("parentesco_apoderado_2_raw", ""))

                        if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                            r_up = requests.put(
                                f"{API_URL}/api/v1/catequizandos/{cat_obj['ID']}",
                                json={
                                    "dni": edit_dni.strip(),
                                    "nombres": edit_nom.strip(),
                                    "apellidos": edit_ape.strip(),
                                    "colegio": edit_col,
                                    "estado_bautismo": edit_baut,
                                    "celular_joven": edit_cel_j.strip() or None,
                                    "celular_apoderado_1": edit_cel_ap1.strip() or None,
                                    "parentesco_apoderado_1": edit_par_ap1.strip() or None,
                                    "celular_apoderado_2": edit_cel_ap2.strip() or None,
                                    "parentesco_apoderado_2": edit_par_ap2.strip() or None,
                                },
                                timeout=15
                            )
                            if r_up.status_code == 200:
                                st.cache_data.clear()
                                st.success("Datos actualizados correctamente.")
                                st.rerun()
                            else:
                                st.error(r_up.json().get("detail", "Error al actualizar."))

                    if st.button("🗑️ Eliminar este Catequizando", type="secondary", key=f"btn_del_cat_{cat_obj['ID']}"):
                        r_del = requests.delete(f"{API_URL}/api/v1/catequizandos/{cat_obj['ID']}", timeout=15)
                        if r_del.status_code == 200:
                            st.cache_data.clear()
                            st.success("Catequizando eliminado.")
                            st.rerun()
                        else:
                            st.error(r_del.json().get("detail", "No se pudo eliminar."))
        else:
            st.warning("Aún no hay catequizandos registrados.")
    else:
        st.error("No se pudo cargar el directorio.")