import pandas as pd
import requests
import streamlit as st
from utils.api import API_URL, api_get
from utils.estilos import mostrar_encabezado_modulo, selector_con_buscador
from utils.reportes import mostrar_botones_exportacion


def mostrar_secretaria():
    mostrar_encabezado_modulo(
        "Módulo de Secretaría",
        "Control de expedientes y documentos requisito",
        "assets/corazon.jpg",
    )

    tab_exp, tab_docs = st.tabs(["📋 Control de Expedientes", "⚙️ Catálogo de Documentos Requisito"])

    lista_docs = api_get("/api/v1/secretaria/documentos") or []

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
                        st.cache_data.clear()
                        st.success("Documento agregado al catálogo.")
                        st.rerun()
                    else:
                        st.error(f"Error ({r.status_code}): {r.text}")

        if lista_docs:
            st.dataframe(pd.DataFrame(lista_docs), use_container_width=True, hide_index=True)
            with st.expander("🗑️ Eliminar Documento del Catálogo"):
                opciones_del_doc = {f"{d['nombre_doc']} (ID: {d['id_doc']})": d["id_doc"] for d in lista_docs}
                id_doc_sel = selector_con_buscador("Documento a eliminar", opciones_del_doc, "del_doc", placeholder="Buscar documento...")
                if id_doc_sel and st.button("Eliminar Documento", key="btn_del_doc"):
                    r_del = requests.delete(
                        f"{API_URL}/api/v1/secretaria/documentos/{id_doc_sel}",
                        timeout=15
                    )
                    if r_del.status_code == 200:
                        st.cache_data.clear()
                        st.success("Documento eliminado del catálogo.")
                        st.rerun()
                    else:
                        st.error(r_del.json().get("detail", "No se pudo eliminar."))
        else:
            st.info("Aún no hay documentos requisito registrados para este año.")

    with tab_exp:
        lista_jovenes = api_get("/api/v1/catequizandos") or []

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
                                "id_usuario": st.session_state.get("admin_id", 1)
                            },
                            timeout=15
                        )
                        if resp_e.status_code in [200, 201]:
                            st.cache_data.clear()
                            st.success("Expediente actualizado correctamente.")
                            st.rerun()
                        else:
                            st.error(f"Error ({resp_e.status_code}): {resp_e.text}")
            else:
                st.warning("Necesitas tener al menos un catequizando y un documento en el catálogo.")

        st.subheader("Consultar Expediente por Catequizando")
        if lista_jovenes:
            opciones_consulta = {f"{j['Nombres']} {j['Apellidos']} (DNI: {j['DNI']})": j for j in lista_jovenes}
            cat_consulta = selector_con_buscador("Catequizando a consultar", opciones_consulta, "consulta_exp")

            if cat_consulta:
                dni_consulta = cat_consulta["DNI"]
                nombre_consulta = f"{cat_consulta['Nombres']} {cat_consulta['Apellidos']}"
                resp_exp = requests.get(f"{API_URL}/api/v1/secretaria/expedientes/{dni_consulta}", timeout=15)
                if resp_exp.status_code == 200:
                    docs_alumno = resp_exp.json().get("documentos", [])
                    if docs_alumno:
                        df_exp = pd.DataFrame(docs_alumno)
                        st.dataframe(df_exp, use_container_width=True, hide_index=True)
                        mostrar_botones_exportacion(df_exp, f"expediente_{dni_consulta}", f"Expediente - {nombre_consulta}")

                        with st.expander("🗑️ Eliminar Registro de Expediente"):
                            opciones_del_exp = {
                                f"ID {d['id_exp']} - {d['documento']} ({d['estado']})": d["id_exp"]
                                for d in docs_alumno if "id_exp" in d
                            }
                            if opciones_del_exp:
                                id_exp_sel = selector_con_buscador("Registro de expediente a eliminar", opciones_del_exp, "del_exp")
                                if id_exp_sel and st.button("Eliminar Registro", key="btn_del_exp"):
                                    r_del = requests.delete(
                                        f"{API_URL}/api/v1/secretaria/expedientes/{id_exp_sel}",
                                        timeout=15
                                    )
                                    if r_del.status_code == 200:
                                        st.cache_data.clear()
                                        st.success("Registro de expediente eliminado.")
                                        st.rerun()
                                    else:
                                        st.error(f"No se pudo eliminar ({r_del.status_code}): {r_del.text}")
                    else:
                        st.info("Este catequizando aún no tiene documentos registrados.")
                else:
                    st.error("No se pudo consultar el expediente.")