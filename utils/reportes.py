from io import BytesIO
import pandas as pd
import qrcode
import streamlit as st
from fpdf import FPDF
from utils.api import ahora_peru

def generar_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Reporte")
    return output.getvalue()

def generar_pdf(df: pd.DataFrame, titulo: str) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    titulo_limpio = titulo.encode("latin-1", "replace").decode("latin-1")
    pdf.cell(0, 10, f"ERP Parroquial - {titulo_limpio}", ln=True, align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Generado el: {ahora_peru().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(4)

    columnas = list(df.columns)
    ancho_util = 277
    ancho_col = ancho_util / max(len(columnas), 1)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    for col in columnas:
        texto = str(col)[:22].encode("latin-1", "replace").decode("latin-1")
        pdf.cell(ancho_col, 7, texto, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for _, fila in df.iterrows():
        for col in columnas:
            valor = str(fila[col])[:28].encode("latin-1", "replace").decode("latin-1")
            pdf.cell(ancho_col, 6, valor, border=1, align="L")
        pdf.ln()

    return bytes(pdf.output())

def mostrar_botones_exportacion(df: pd.DataFrame, nombre_base: str, titulo_pdf: str):
    c1, c2, _ = st.columns([1, 1, 3])
    fecha = ahora_peru().strftime("%Y%m%d")
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

def _limpiar_texto_pdf(texto: str) -> str:
    return str(texto).encode("latin-1", "replace").decode("latin-1")

def _dibujar_carnet(pdf: FPDF, x: float, y: float, alumno: dict):
    ancho, alto = 85, 54

    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, ancho, alto)

    # Franja superior roja
    pdf.set_fill_color(170, 24, 24)
    pdf.rect(x, y, ancho, 11, style="F")

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_xy(x, y + 2.5)
    pdf.cell(ancho, 6, _limpiar_texto_pdf("PARROQUIA - CONFIRMACION"), align="C")

    img_qr = qrcode.make(alumno["QR Token"])
    buf_qr = BytesIO()
    img_qr.save(buf_qr, format="PNG")
    buf_qr.seek(0)
    pdf.image(buf_qr, x=x + 3, y=y + 14, w=34, h=34)

    pdf.set_text_color(20, 20, 20)
    pdf.set_xy(x + 39, y + 16)
    pdf.set_font("Helvetica", "B", 8)
    pdf.multi_cell(43, 4.2, _limpiar_texto_pdf(alumno["Nombres"].upper()))

    pdf.set_xy(x + 39, y + 26)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(43, 4.2, _limpiar_texto_pdf(alumno["Apellidos"].upper()))

    pdf.set_xy(x + 39, y + 38)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(43, 5, f"DNI: {alumno['DNI']}")

    pdf.set_xy(x + 39, y + 43)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(43, 4, _limpiar_texto_pdf(alumno["QR Token"]))

def generar_carnet_individual_pdf(alumno: dict) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format=(85, 54))
    pdf.set_auto_page_break(False)
    pdf.add_page()
    _dibujar_carnet(pdf, 0, 0, alumno)
    return bytes(pdf.output())

def generar_carnets_bloque_pdf(lista_alumnos: list) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)

    pos_x = [15, 110]
    pos_y = [11, 67, 123, 179, 235]

    for idx, alumno in enumerate(lista_alumnos):
        pos_en_hoja = idx % 10
        if pos_en_hoja == 0:
            pdf.add_page()
        col = pos_en_hoja % 2
        fila = pos_en_hoja // 2
        _dibujar_carnet(pdf, pos_x[col], pos_y[fila], alumno)

    return bytes(pdf.output())