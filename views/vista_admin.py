import json
from io import BytesIO
import pandas as pd
import requests
import streamlit as st
from utils.api import (
    API_URL,
    ahora_peru,
    COLEGIOS_PARROQUIA,
    TEMAS_CATEQUESIS,
    MISAS_ANUALES,
    ACTIVIDADES_PARROQUIALES,
)
from utils.estilos import selector_con_buscador
from utils.reportes import generar_excel


def mostrar_accesos_temporales():
    st.title("🔐 Accesos Temporales y Turnos APK")

    tab_apk, tab_web = st.tabs([
        "📱 Códigos de Servicio APK (Máx. 4h)",
        "🌐 Claves Temporales Web"
    ])

    # --- PESTAÑA 1: CÓDIGOS DE SERVICIO PARA LA APK ---
    with tab_apk:
        st.subheader("Generar Código de Servicio para Catequistas / Vocales")
        st.caption("El código amarra la APK al evento elegido y cierra la sesión automáticamente al vencer (máx. 4 horas).")

        c1, c2 = st.columns(2)
        tipo_srv = c1.selectbox(
            "Evento del turno",
            ["Catequesis", "Misa", "Actividad Parroquial"],
            key="srv_tipo"
        )
        if tipo_srv == "Catequesis":
            detalle_srv = c2.selectbox("Número de Tema", TEMAS_CATEQUESIS, key="srv_detalle_tema")
        elif tipo_srv == "Misa":
            detalle_srv = c2.selectbox("Número de Misa", MISAS_ANUALES, key="srv_detalle_misa")
        else:
            detalle_srv = c2.selectbox("Actividad específica", ACTIVIDADES_PARROQUIALES, key="srv_detalle_act")

        colegio_srv = st.selectbox(
            "Colegio permitido para este código",
            ["Todos"] + COLEGIOS_PARROQUIA,
            key="srv_colegio"
        )

        c3, c4, c5 = st.columns([1, 1, 1])
        duracion_srv = c3.selectbox("Duración del turno", [1, 2, 3, 4], index=3, format_func=lambda h: f"{h} hora(s)", key="srv_dur")
        usar_tardanza = c4.checkbox("Activar límite de tardanza", value=False, key="srv_chk_tard")
        hora_limite_str = None
        if usar_tardanza:
            hora_lim = c5.time_input("Tardanza a partir de (Hora Perú):", key="srv_hora_lim")
            hora_limite_str = hora_lim.strftime("%H:%M")

        if st.button("🔑 Generar Código de Servicio APK", type="primary", key="btn_gen_srv"):
            r_srv = requests.post(
                f"{API_URL}/api/v1/admin/codigos-servicio",
                json={
                    "tipo_asistencia": tipo_srv,
                    "colegio_permitido": colegio_srv,
                    "detalle_evento": detalle_srv,
                    "duracion_horas": duracion_srv,
                    "hora_limite_tardanza": hora_limite_str
                },
                timeout=15
            )
            if r_srv.status_code == 200:
                d = r_srv.json()
                st.success(
                    f"Código generado: **{d['codigo']}** | Evento: **{d['evento']}** | "
                    f"Tardanza desde: **{d['hora_limite_tardanza']}** | Expira (Perú): **{d['expira_peru']}**"
                )
                st.rerun()
            else:
                st.error(f"Error ({r_srv.status_code}): {r_srv.text}")

        st.divider()
        st.subheader("Códigos de Servicio Recientes")
        resp_srv = requests.get(f"{API_URL}/api/v1/admin/codigos-servicio", timeout=15)
        if resp_srv.status_code == 200 and resp_srv.json():
            lista_srv = resp_srv.json()
            st.dataframe(pd.DataFrame(lista_srv), use_container_width=True, hide_index=True)

            activos_srv = [c for c in lista_srv if c["Estado"] == "Activo"]
            if activos_srv:
                opciones_rev_srv = {
                    f"{c['Código']} - {c['Evento']} (Expira: {c['Expira (Perú)']})": c["ID"]
                    for c in activos_srv
                }
                srv_rev = st.selectbox("Revocar un código activo en vivo:", list(opciones_rev_srv.keys()), key="sel_rev_srv")
                if st.button("🚫 Revocar Código APK Ahora", key="btn_rev_srv"):
                    r_rev = requests.put(
                        f"{API_URL}/api/v1/admin/codigos-servicio/{opciones_rev_srv[srv_rev]}/revocar",
                        timeout=15
                    )
                    if r_rev.status_code == 200:
                        st.success("Código revocado. Cualquier celular usándolo será expulsado al intentar escanear.")
                        st.rerun()
                    else:
                        st.error("No se pudo revocar el código.")
        else:
            st.info("Aún no hay códigos de servicio generados.")

    # --- PESTAÑA 2: CLAVES TEMPORALES PARA EL DASHBOARD WEB ---
    with tab_web:
        st.subheader("Claves Temporales del Dashboard Web")
        st.caption("Genera códigos para que otros roles puedan acceder temporalmente a todos los módulos web.")

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


def mostrar_gestion_usuarios():
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
        id_u_eliminar = selector_con_buscador("Usuario a eliminar", opciones_del, "del_usuario", placeholder="Buscar por DNI, nombre o rol...")
        if id_u_eliminar and st.button("🗑️ Eliminar Usuario Seleccionado"):
            r_del = requests.delete(
                f"{API_URL}/api/v1/admin/usuarios/{id_u_eliminar}",
                timeout=15
            )
            if r_del.status_code == 200:
                st.success("Usuario eliminado.")
                st.rerun()
            else:
                st.error(f"No se pudo eliminar ({r_del.status_code}): {r_del.text}")
    else:
        st.info("No hay usuarios registrados.")


def mostrar_respaldo():
    st.title("💾 Respaldo y Restauración de Base de Datos")
    st.caption("Descarga copias de seguridad completas o restaura el sistema ante cualquier imprevisto.")

    tab_bk, tab_rest, tab_imp = st.tabs([
        "📦 Descargar Copia de Seguridad",
        "♻️ Restaurar desde Backup (.json)",
        "📥 Importar Catequizandos (.xlsx)"
    ])

    with tab_bk:
        st.subheader("Generar Respaldo Completo")
        st.write(
            "- **Backup Técnico (`.json`):** Sirve para restaurar exactamente toda la base de datos (roles, usuarios, catequizandos, asistencias, pagos y expedientes).\n"
            "- **Respaldo Legible (`.xlsx`):** Archivo Excel con todas las tablas en pestañas separadas para archivo local."
        )

        if st.button("🔄 Generar Copia de Seguridad Ahora", type="primary"):
            with st.spinner("Extrayendo todas las tablas desde TiDB Cloud..."):
                r_bk = requests.get(f"{API_URL}/api/v1/admin/backup/exportar", timeout=30)

            if r_bk.status_code == 200:
                backup_data = r_bk.json()
                fecha_tag = ahora_peru().strftime("%Y%m%d_%H%M")

                json_bytes = json.dumps(backup_data, indent=2, ensure_ascii=False).encode("utf-8")

                excel_buf = BytesIO()
                with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
                    for tabla in [
                        "catequizandos", "asistencias", "pagos",
                        "expedientes", "conceptos_pago", "documentos_requisito",
                        "usuarios", "roles"
                    ]:
                        df_t = pd.DataFrame(backup_data.get(tabla, []))
                        df_t.to_excel(writer, index=False, sheet_name=tabla[:31])
                excel_bytes = excel_buf.getvalue()

                st.success("Copia de seguridad generada correctamente.")
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button(
                        label="⬇️ Descargar Backup Técnico (.json)",
                        data=json_bytes,
                        file_name=f"backup_erp_parroquia_{fecha_tag}.json",
                        mime="application/json"
                    )
                with c2:
                    st.download_button(
                        label="📊 Descargar Respaldo Completo (.xlsx)",
                        data=excel_bytes,
                        file_name=f"respaldo_erp_parroquia_{fecha_tag}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.error(f"Error al generar respaldo ({r_bk.status_code}): {r_bk.text}")

    with tab_rest:
        st.subheader("Restaurar Base de Datos desde Archivo `.json`")
        st.warning("Esta operación inserta los registros faltantes respetando sus IDs y relaciones originales. Los registros que ya existan en la base de datos se omiten sin sobrescribirse.")

        archivo_json = st.file_uploader("Selecciona tu archivo backup_erp_parroquia_*.json", type=["json"])
        if archivo_json is not None:
            try:
                contenido = json.loads(archivo_json.read().decode("utf-8"))
                st.info(
                    f"**Fecha del respaldo (Perú):** {contenido.get('fecha_backup_peru') or contenido.get('fecha_backup', 'Desconocida')} | "
                    f"**Catequizandos:** {len(contenido.get('catequizandos', []))} | "
                    f"**Asistencias:** {len(contenido.get('asistencias', []))} | "
                    f"**Pagos:** {len(contenido.get('pagos', []))}"
                )
                confirmar = st.checkbox("Confirmo que deseo restaurar estos datos en la base de datos actual.")
                if confirmar and st.button("♻️ Iniciar Restauración", type="primary"):
                    with st.spinner("Restaurando tablas en orden de dependencias..."):
                        r_res = requests.post(
                            f"{API_URL}/api/v1/admin/backup/restaurar",
                            json=contenido,
                            timeout=60
                        )
                    if r_res.status_code == 200:
                        st.cache_data.clear()
                        st.success("¡Restauración completada!")
                        st.json(r_res.json().get("registros_restaurados", {}))
                    else:
                        st.error(f"Error ({r_res.status_code}): {r_res.text}")
            except Exception as e:
                st.error(f"Archivo JSON inválido: {e}")

    with tab_imp:
        st.subheader("Importación Masiva de Catequizandos desde Excel")
        st.caption(
            "Columnas obligatorias: **DNI**, **Nombres**, **Apellidos**. "
            "Columnas opcionales: **Colegio**, **Bautismo**, **Celular Joven**, **Celular Apoderado 1**, "
            "**Parentesco Apoderado 1**, **Celular Apoderado 2**, **Parentesco Apoderado 2**, **Grupo**, **Salón**."
        )

        df_plantilla = pd.DataFrame([
            {
                "DNI": "12345678",
                "Nombres": "Juan Carlos",
                "Apellidos": "Perez Quispe",
                "Colegio": "Mercedes",
                "Bautismo": "Bautizado",
                "Celular Joven": "987654321",
                "Celular Apoderado 1": "912345678",
                "Parentesco Apoderado 1": "Mamá - María",
                "Celular Apoderado 2": "955443322",
                "Parentesco Apoderado 2": "Papá - Juan",
                "Grupo": "Grupo A",
                "Salón": "Salón 1",
            }
        ])
        st.download_button(
            label="📄 Descargar Plantilla Excel Completa",
            data=generar_excel(df_plantilla),
            file_name="plantilla_catequizandos_completa.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        archivo_xlsx = st.file_uploader("Sube tu archivo Excel (.xlsx)", type=["xlsx"])
        if archivo_xlsx is not None:
            try:
                df_imp = pd.read_excel(archivo_xlsx, dtype=str)
                df_imp.columns = [c.strip() for c in df_imp.columns]

                columnas_req = {"DNI", "Nombres", "Apellidos"}
                if not columnas_req.issubset(set(df_imp.columns)):
                    st.error("El Excel debe contener al menos las columnas exactas: DNI, Nombres, Apellidos.")
                else:
                    st.dataframe(df_imp.head(20), use_container_width=True, hide_index=True)
                    st.caption(f"Total de filas detectadas: **{len(df_imp)}**")

                    def _celda(row, col_nombre, default=None):
                        if col_nombre not in row.index:
                            return default
                        val = row[col_nombre]
                        if pd.isna(val):
                            return default
                        texto = str(val).strip()
                        return texto if texto and texto.lower() != "nan" else default

                    if st.button("📥 Importar Catequizandos", type="primary"):
                        payload = []
                        for _, row in df_imp.dropna(subset=["DNI", "Nombres", "Apellidos"]).iterrows():
                            dni_val = str(row["DNI"]).strip().split(".")[0].zfill(8)
                            salon_val = _celda(row, "Salón") or _celda(row, "Salon")
                            payload.append({
                                "dni": dni_val,
                                "nombres": str(row["Nombres"]).strip(),
                                "apellidos": str(row["Apellidos"]).strip(),
                                "colegio": _celda(row, "Colegio"),
                                "estado_bautismo": _celda(row, "Bautismo", "Bautizado"),
                                "celular_joven": _celda(row, "Celular Joven"),
                                "celular_apoderado_1": _celda(row, "Celular Apoderado 1"),
                                "parentesco_apoderado_1": _celda(row, "Parentesco Apoderado 1"),
                                "celular_apoderado_2": _celda(row, "Celular Apoderado 2"),
                                "parentesco_apoderado_2": _celda(row, "Parentesco Apoderado 2"),
                                "grupo": _celda(row, "Grupo"),
                                "salon": salon_val,
                            })

                        with st.spinner("Importando catequizandos..."):
                            r_imp = requests.post(
                                f"{API_URL}/api/v1/admin/importar/catequizandos",
                                json=payload,
                                timeout=60
                            )
                        if r_imp.status_code == 200:
                            st.cache_data.clear()
                            res = r_imp.json()
                            st.success(
                                f"Importación terminada: **{res['creados']}** creados, "
                                f"**{res['omitidos']}** omitidos (duplicados o DNI inválido)."
                            )
                        else:
                            st.error(f"Error ({r_imp.status_code}): {r_imp.text}")
            except Exception as e:
                st.error(f"No se pudo leer el archivo Excel: {e}")