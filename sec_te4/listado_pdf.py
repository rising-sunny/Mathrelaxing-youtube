"""Listado PDF de TE4 inscritos: folio, fecha de inscripción y Potencia Total Instalada del EG, con total."""
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from edeclarador import kw_cl


class _CanvasNumerado(Canvas):
    """Agrega "Página X de Y" al pie cuando el documento tiene más de una página."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            if total > 1:
                self.setFont("Helvetica", 8.5)
                self.drawRightString(letter[0] - 2.5 * cm - 6, 1.3 * cm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def generar(ruta, filas, instalador, run, subtitulo, fecha):
    """filas: [(folio, 'dd/mm/aaaa', kW)] en el orden en que deben aparecer."""
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=10, leading=13)
    titulo = ParagraphStyle("titulo", parent=base, fontName="Helvetica-Bold", fontSize=12.5, leading=16, alignment=TA_CENTER)
    centrado = ParagraphStyle("centrado", parent=base, alignment=TA_CENTER)
    nota = ParagraphStyle("nota", parent=base, fontSize=8.5, leading=11)
    firma = ParagraphStyle("firma", parent=base, alignment=TA_CENTER, leading=13.5)
    cabecera = ParagraphStyle("cabecera", parent=base, fontName="Helvetica-Bold", fontSize=9, leading=11, alignment=TA_CENTER)

    datos = Table([["Instalador:", instalador], ["RUN:", run],
                   ["Trámite:", "TE4 – Puesta en servicio de generadoras residenciales"], ["Fecha:", fecha]],
                  colWidths=[2.3 * cm, 12 * cm], hAlign="LEFT")
    datos.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
        ("FONT", (1, 0), (1, -1), "Helvetica", 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))

    total = round(sum(kw for _, _, kw in filas), 2)
    cuerpo = [[str(i), folio, fecha_ins, kw_cl(kw)] for i, (folio, fecha_ins, kw) in enumerate(filas, 1)]
    tabla = Table([[Paragraph(t, cabecera) for t in ("N°", "Folio de inscripción", "Fecha de inscripción",
                                                     "Potencia Total Instalada del EG (kW)")]]
                  + cuerpo + [["Total", "", "", kw_cl(total)]],
                  colWidths=[1.4 * cm, 4.2 * cm, 4.2 * cm, 6.36 * cm], repeatRows=1)
    ultima = len(cuerpo) + 1
    tabla.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (2, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("RIGHTPADDING", (3, 1), (3, -1), 14),
        ("TOPPADDING", (0, 1), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("SPAN", (0, ultima), (2, ultima)),
        ("ALIGN", (0, ultima), (2, ultima), "RIGHT"),
        ("RIGHTPADDING", (0, ultima), (2, ultima), 10),
        ("FONT", (0, ultima), (-1, ultima), "Helvetica-Bold", 9.5),
        ("BACKGROUND", (0, ultima), (-1, ultima), colors.HexColor("#F2F2F2")),
    ]))

    story = [
        Paragraph("DECLARACIONES TE4 INSCRITAS ANTE LA SEC", titulo),
        Spacer(1, 3),
        Paragraph(subtitulo, centrado),
        Spacer(1, 20),
        datos,
        Spacer(1, 16),
        tabla,
        Spacer(1, 10),
        KeepTogether([
            Paragraph("Fuente: certificados de inscripción TE4 emitidos por la Superintendencia de Electricidad y "
                      "Combustibles (SEC), obtenidos desde la plataforma e-Declarador. La potencia indicada corresponde "
                      "al campo “Potencia Total Instalada del EG (kW)” de la sección 3 de cada certificado.", nota),
            Spacer(1, 70),
            Paragraph("_______________________________", firma),
            Paragraph(instalador, firma),
            Paragraph(f"RUN {run}", firma),
            Paragraph("Instalador eléctrico autorizado SEC", firma),
        ]),
    ]
    doc = SimpleDocTemplate(str(ruta), pagesize=letter, leftMargin=2.5 * cm, rightMargin=2.5 * cm,
                            topMargin=2.2 * cm, bottomMargin=2 * cm, title="Declaraciones TE4 inscritas",
                            author=instalador, subject="Listado de declaraciones TE4", creator=instalador)
    doc.build(story, canvasmaker=_CanvasNumerado)
