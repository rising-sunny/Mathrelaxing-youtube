"""Descarga los certificados de inscripción TE4 (PDF) desde el e-Declarador de la SEC.

Instalación (una vez):
    pip install playwright pypdf
    playwright install chromium

Uso:
    python sec_te4/descargar_te4.py                    # todos los certificados del listado
    python sec_te4/descargar_te4.py --min-kw 10        # deja aparte los de Potencia Total Instalada del EG >= 10 kW
    python sec_te4/descargar_te4.py --folios 123,456   # solo esos folios de inscripción
    python sec_te4/descargar_te4.py --manual           # entras tú (p. ej. con ClaveÚnica) y el script descarga

El RUT y la clave se leen de las variables de entorno SEC_RUT y SEC_PASSWORD; si no están, se piden
por consola. Los PDF quedan en sec_te4/certificados/TE4_<folio>.pdf (carpeta ignorada por git). Con
--min-kw, los de menor potencia pasan a certificados/bajo_minimo/ y los que no se pudieron
leer con seguridad a certificados/revisar/.
"""
import argparse
import getpass
import importlib.util
import logging
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

try:
    from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright
except ImportError:
    sys.exit("Falta Playwright: pip install playwright && playwright install chromium")
logging.getLogger("pypdf").setLevel(logging.ERROR)  # pypdf solo se usa con --min-kw

AQUI = Path(__file__).resolve().parent
DEBUG = AQUI / "debug"
URL_LOGIN = "https://wlhttp.sec.cl/edeclaradorTE4/declarador.jsp"
MENU_INSCRITAS = (r"^\s*declaraciones\s+inscritas\b", r"inscrit")
BOTON_BUSCAR = (r"^\s*buscar\s*$", r"buscar")
BOTON_PDF = (r"imprimir", r"\bpdf\b|descargar")  # en la ventana "Firma digital SEC" del certificado
AVISOS = []  # mensajes alert() del sitio

# Marca con data-te4="i" el ícono "Ver Certificado" de cada fila del listado y devuelve los folios.
JS_TABLA = r"""() => {
  const norm = s => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
  const CLIC = "a,button,input:not([type=hidden]),img,[onclick]";
  const esCert = e => /certific/i.test(e.outerHTML);
  document.querySelectorAll("[data-te4]").forEach(e => e.removeAttribute("data-te4"));
  const marcar = filas => filas.map(([folio, el], i) => { el.setAttribute("data-te4", i); return folio; });
  for (const t of document.querySelectorAll("table")) {
    const filas = Array.from(t.rows);
    const h = filas.findIndex(r => r.cells.length >= 3 && Array.from(r.cells).some(c => {
      const x = norm(c.innerText); return x.length < 40 && x.includes("folio"); }));
    if (h < 0) continue;
    const cab = Array.from(filas[h].cells).map(c => norm(c.innerText));
    let cf = cab.findIndex(x => x.includes("folio") && x.includes("inscrip"));
    if (cf < 0) cf = cab.findIndex(x => x.includes("folio"));
    const cc = cab.findIndex(x => x.length < 40 && x.includes("certificado"));
    const res = [];
    for (const r of filas.slice(h + 1)) {
      const m = r.cells.length > cf && norm(r.cells[cf].innerText).match(/\d+/);
      if (!m) continue;
      const el = cc >= 0 ? r.cells[cc] && r.cells[cc].querySelector(CLIC)
                         : Array.from(r.querySelectorAll(CLIC)).find(esCert);
      if (el) res.push([m[0], el]);
    }
    if (res.length) return marcar(res);
  }
  const res = [];  // sin cabecera reconocible: filas con un enlace "certific..." y una celda numérica
  for (const r of document.querySelectorAll("tr")) {
    const el = !r.querySelector("table") && Array.from(r.querySelectorAll(CLIC)).find(esCert);
    const c = el && Array.from(r.cells).find(c => /^\d{2,}$/.test(norm(c.innerText)));
    if (c) res.push([norm(c.innerText), el]);
  }
  return marcar(res);
}"""

# Marca con data-te4-sig el control de página siguiente; devuelve "sig", "fin" (última página) o "".
JS_SIGUIENTE = r"""() => {
  const norm = s => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
  document.querySelectorAll("[data-te4-sig]").forEach(e => e.removeAttribute("data-te4-sig"));
  const m = norm(document.body && document.body.innerText).match(/p[aá]gina\s*(\d+)\s*de\s*(\d+)/);
  if (m && +m[1] >= +m[2]) return "fin";
  const texto = e => norm([e.innerText, e.value, e.alt, e.title, (e.getAttribute("src") || "").split("/").pop()]
    .filter(Boolean).join(" "));
  const cands = Array.from(document.querySelectorAll("a,button,input:not([type=hidden]),img,[onclick]"));
  const el = (m && cands.find(e => texto(e) === String(+m[1] + 1))) ||
             cands.find(e => /siguiente|next|›|»|►/.test(texto(e)) && !/[uú]ltim|last/.test(texto(e)));
  if (!el) return "";
  el.setAttribute("data-te4-sig", "");
  return "sig";
}"""

# Marca con data-te4-btn el primer elemento clicable cuyo texto calce con el patrón.
JS_MARCAR = r"""(patron) => {
  const rx = new RegExp(patron, "i");
  document.querySelectorAll("[data-te4-btn]").forEach(e => e.removeAttribute("data-te4-btn"));
  const texto = e => [e.innerText, e.value, e.alt, e.title, (e.getAttribute("src") || "").split("/").pop()]
    .filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
  const cands = Array.from(document.querySelectorAll("a,button,input:not([type=hidden]),img,[onclick]"))
    .filter(e => { const t = texto(e); return t.length < 80 && rx.test(t); });
  const el = cands.find(e => e.matches("a,button,input,[onclick]")) || cands[0];
  if (!el) return false;
  el.setAttribute("data-te4-btn", "");
  return true;
}"""


def aviso(dialog):
    AVISOS.append(dialog.message)
    print(f"  [SEC] {dialog.message}")
    dialog.accept()


def esperar(page):
    page.wait_for_timeout(800)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        pass


def clic(loc):
    try:
        loc.click(timeout=5000)
    except Exception:
        try:
            loc.evaluate("e => e.click()")  # p. ej. ítems de menú ocultos hasta pasar el mouse
        except Exception:
            pass


def clic_texto(page, patrones):
    """Clickea el primer elemento (en cualquier frame) cuyo texto calce con alguno de los patrones."""
    for patron in patrones:
        for fr in page.frames:
            try:
                encontrado = fr.evaluate(JS_MARCAR, patron)
            except Exception:
                continue
            if encontrado:
                clic(fr.locator("[data-te4-btn]").first)
                esperar(page)
                return True
    return False


def buscar_tabla(page):
    """Devuelve (frame, folios) del listado de declaraciones inscritas visible, o (None, [])."""
    for fr in page.frames:
        try:
            folios = fr.evaluate(JS_TABLA)
        except Exception:
            continue
        if folios:
            return fr, folios
    return None, []


def esperar_listado(page, segundos):
    fin = time.time() + segundos
    while time.time() < fin:
        if buscar_tabla(page)[1]:
            return True
        page.wait_for_timeout(1000)
    return False


def volcar_debug(page, etiqueta):
    """Guarda captura y HTML de cada frame en sec_te4/debug/ para ajustar el script si el sitio cambia."""
    DEBUG.mkdir(exist_ok=True)
    base = DEBUG / f"{time.strftime('%H%M%S')}_{etiqueta}"
    try:
        page.screenshot(path=f"{base}.png", full_page=True)
    except Exception:
        pass
    for i, fr in enumerate(page.frames):
        try:
            Path(f"{base}_frame{i}.html").write_text(fr.content(), encoding="utf-8")
        except Exception:
            pass
    print(f"  (captura y HTML guardados en {DEBUG}; contienen datos personales)")


def login(page, url, rut, clave):
    page.goto(url)
    page.fill("input[name=declaRut]", rut)
    page.fill("input[name=password]", clave)
    inicial, n_avisos = page.url.split("#")[0], len(AVISOS)
    try:
        page.evaluate("() => { enviarForm('ingresar_usuario'); }")  # lo mismo que hace el botón INGRESAR
    except Exception:
        pass  # la navegación del login puede cortar el evaluate
    if len(AVISOS) == n_avisos:  # sin alert de validación: el formulario se envió
        try:
            page.wait_for_url(lambda u: u.split("#")[0] != inicial, timeout=30000)
        except PWTimeout:
            pass
    esperar(page)
    if not page.locator("input[name=declaRut]").count():
        print("Sesión iniciada.")
        return True
    motivos = [l.strip() for l in page.inner_text("body").splitlines()
               if re.search(r"error|incorrect|inv[aá]lid|bloque|no existe|expir", l, re.I)]
    print("No se pudo iniciar sesión.", *(motivos + AVISOS[n_avisos:])[-3:], sep="\n  ")
    volcar_debug(page, "login")
    return False


def preparar_listado(page, args):
    """Desde el menú entra a 'Declaraciones Inscritas', filtra por TE4 y ejecuta la búsqueda."""
    for patrones in (MENU_INSCRITAS, BOTON_BUSCAR):
        if buscar_tabla(page)[1]:
            return
        if patrones is BOTON_BUSCAR:  # el listado también trae TE6/TE7: se elige "TE4" en el tipo de trámite
            for fr in page.frames:
                try:
                    fr.evaluate(r"""() => { for (const s of document.querySelectorAll("select"))
                      for (const o of s.options) if (/\bTE-?4\b/i.test(o.text)) s.value = o.value; }""")
                except Exception:
                    pass
        if clic_texto(page, patrones) and args.debug:
            volcar_debug(page, "paso")
    if esperar_listado(page, 10):
        return
    volcar_debug(page, "sin_listado")
    if args.headless:
        sys.exit("No encontré el listado de declaraciones inscritas.")
    print("No pude llegar solo al listado: en el navegador abre 'Declaraciones Inscritas' y presiona Buscar.")
    if not esperar_listado(page, 15 * 60):
        sys.exit("No apareció el listado de declaraciones inscritas.")


def capturar_pdf(contexto, page, elemento, timeout_s, etiqueta):
    """Clickea el ícono del certificado y devuelve el primer PDF que entregue el servidor (o None).

    Mientras dura el clic se interceptan las respuestas, así da igual si el sitio abre el PDF en una
    ventana nueva, en la misma pestaña, dentro de un iframe o como descarga.
    """
    pdfs = []

    def interceptar(route):
        if route.request.resource_type not in ("document", "xhr", "fetch", "other"):
            return route.continue_()
        try:
            resp = route.fetch()
            cuerpo = resp.body()
        except Exception:
            return route.continue_()
        inicio = cuerpo.find(b"%PDF", 0, 1024)
        if inicio < 0:
            return route.fulfill(response=resp)
        pdfs.append(cuerpo[inicio:])
        route.fulfill(status=204)  # sin visor ni descarga: el navegador se queda en el listado

    antes = set(contexto.pages)
    contexto.route("**/*", interceptar)
    try:
        clic(elemento)
        fin, impreso = time.time() + timeout_s, False
        while not pdfs and time.time() < fin:
            page.wait_for_timeout(250)
            nuevas = [p for p in contexto.pages if p not in antes and p.url != "about:blank"]
            if nuevas and not impreso:
                # la SEC abre el certificado como página HTML ("Firma digital SEC"): el PDF sale de su botón Imprimir
                try:
                    nuevas[-1].wait_for_load_state(timeout=15000)
                except PWTimeout:
                    pass
                impreso = bool(pdfs) or clic_texto(nuevas[-1], BOTON_PDF)
    finally:
        contexto.unroute("**/*", interceptar)
        for p in contexto.pages:
            if p not in antes:
                if not pdfs:
                    volcar_debug(p, etiqueta + "_ventana")
                p.close()
    if not pdfs:
        volcar_debug(page, etiqueta)
    return pdfs[0] if pdfs else None


def siguiente_pagina(page, fr, headless):
    try:
        estado = fr.evaluate(JS_SIGUIENTE)
    except Exception:
        estado = ""
    if estado == "fin":
        return False
    if estado == "sig":
        clic(fr.locator("[data-te4-sig]").first)
        esperar(page)
        return True
    if headless:
        return False
    r = input("¿Hay más páginas? Avanza a la siguiente en el navegador y presiona Enter (o escribe q para terminar): ")
    return r.strip().lower() != "q"


def descargar(contexto, page, destino, buscados, args):
    ok, omitidos, fallidos, vistas = [], [], [], set()
    while True:
        fr, folios = buscar_tabla(page)
        if not folios or tuple(folios) in vistas:
            break
        vistas.add(tuple(folios))
        print(f"Página {len(vistas)}: {len(folios)} certificados en el listado")
        for folio in folios:
            ruta = destino / f"TE4_{folio}.pdf"
            if buscados and folio not in buscados:
                continue
            previos = [destino / sub / ruta.name for sub in ("", "bajo_minimo", "revisar")]
            if not args.forzar and any(p.exists() and p.stat().st_size for p in previos):
                omitidos.append(folio)
                continue
            fr, actuales = buscar_tabla(page)  # vuelve a marcar las filas por si la página se recargó
            pdf = folio in actuales and capturar_pdf(
                contexto, page, fr.locator(f'[data-te4="{actuales.index(folio)}"]').first,
                args.timeout, f"folio_{folio}")
            if pdf:
                ruta.write_bytes(pdf)
                ok.append(folio)
                print(f"  OK     {ruta.name}  ({len(pdf) / 1024:.0f} KB)")
            else:
                fallidos.append(folio)
                print(f"  ERROR  folio {folio}: el sitio no entregó un PDF")
        if buscados and buscados <= set(ok + omitidos + fallidos):
            break
        if not siguiente_pagina(page, fr, args.headless):
            break
    return ok, omitidos, fallidos


def potencias_eg(ruta):
    """Valores (kW) de 'Potencia Total Instalada del EG' (sección 3, Detalle de Instalaciones) del certificado."""
    from pypdf import PdfReader
    try:
        texto = " ".join(p.extract_text() or "" for p in PdfReader(ruta).pages)
    except Exception:
        return set()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    for rotulo in (r"potencia\s+total\s+instalada\s+del\s+eg", r"potencia\s+total\s+instalada"):
        valores = set()
        for m in re.finditer(rotulo, texto):
            n = re.search(r"\d+(?:[.,]\d+)?", texto[m.end():m.end() + 60])
            if n:
                valores.add(float(n.group().replace(",", ".")))
        if valores:
            return valores
    return set()


def clasificar(destino, min_kw):
    """Deja en `destino` solo los certificados con potencia instalada del EG >= min_kw; el resto va a subcarpetas.

    Si el PDF no trae el valor o trae varios distintos, va a revisar/ en vez de adivinar.
    """
    bajo, revisar = destino / "bajo_minimo", destino / "revisar"
    elegidos, dudosos, n_bajo = [], [], 0
    for pdf in sorted({p for d in (destino, bajo, revisar) for p in d.glob("TE4_*.pdf")}, key=lambda p: p.name):
        valores = potencias_eg(pdf)
        kw = valores.pop() if len(valores) == 1 else None
        if kw is None:
            carpeta = revisar
            dudosos.append(f"{pdf.name}  {sorted(valores) if valores else 'sin dato'}")
        elif kw >= min_kw:
            carpeta = destino
            elegidos.append(f"{pdf.name}  {kw:g} kW")
        else:
            carpeta, n_bajo = bajo, n_bajo + 1
        carpeta.mkdir(exist_ok=True)
        pdf.replace(carpeta / pdf.name)
    print(f"\nPotencia Total Instalada del EG >= {min_kw:g} kW: {len(elegidos)} certificados (quedan en {destino})")
    for linea in elegidos:
        print("  " + linea)
    print(f"Bajo {min_kw:g} kW: {n_bajo} (movidos a {bajo})")
    if dudosos:
        print(f"No pude leer la potencia instalada del EG con seguridad; revísalos a mano en {revisar}:")
        for linea in dudosos:
            print("  " + linea)


def main():
    ap = argparse.ArgumentParser(description="Descarga certificados TE4 (PDF) desde el e-Declarador SEC.")
    ap.add_argument("--min-kw", type=lambda s: float(s.replace(",", ".")),
                    help="deja en la carpeta solo los de Potencia Total Instalada del EG >= este valor en kW (ej. 10)")
    ap.add_argument("--folios", help="folios de inscripción separados por coma (por defecto, todos)")
    ap.add_argument("--manual", action="store_true",
                    help="inicias sesión y buscas tú en el navegador; el script descarga el listado")
    ap.add_argument("--salida", default=str(AQUI / "certificados"), help="carpeta de destino de los PDF")
    ap.add_argument("--forzar", action="store_true", help="vuelve a descargar los PDF que ya existen")
    ap.add_argument("--headless", action="store_true", help="sin abrir ventana del navegador")
    ap.add_argument("--timeout", type=int, default=60, help="segundos de espera por certificado (defecto 60)")
    ap.add_argument("--debug", action="store_true", help="guarda captura y HTML de cada paso en sec_te4/debug/")
    ap.add_argument("--url", default=URL_LOGIN, help="página de ingreso (por si la SEC la cambia)")
    args = ap.parse_args()
    if args.manual and args.headless:
        ap.error("--manual necesita ver el navegador (quita --headless)")
    if args.min_kw is not None and importlib.util.find_spec("pypdf") is None:
        ap.error("--min-kw necesita pypdf: pip install pypdf")

    buscados = {re.sub(r"\D", "", f) for f in args.folios.split(",")} - {""} if args.folios else set()
    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)
    if not args.manual:
        rut = os.environ.get("SEC_RUT") or input("RUT del instalador (ej. 12345678-9): ").strip()
        clave = os.environ.get("SEC_PASSWORD") or getpass.getpass("Clave e-Declarador: ")

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=args.headless)
        contexto = navegador.new_context(accept_downloads=True)
        contexto.on("page", lambda pg: pg.on("dialog", aviso))
        page = contexto.new_page()
        if args.manual:
            page.goto(urljoin(args.url, "usuario_declarador.jsp"))
            print("Inicia sesión en el navegador, abre 'Declaraciones Inscritas' y presiona Buscar.")
            if not esperar_listado(page, 15 * 60):
                sys.exit("No apareció el listado de declaraciones inscritas.")
        else:
            if not login(page, args.url, rut, clave):
                sys.exit(1)
            preparar_listado(page, args)
        ok, omitidos, fallidos = descargar(contexto, page, destino, buscados, args)
        navegador.close()

    print(f"\nDescargados: {len(ok)} | ya existían: {len(omitidos)} | con error: {len(fallidos)}  ->  {destino}")
    if fallidos:
        print("Folios con error:", ", ".join(fallidos), f"(detalle en {DEBUG})")
    faltan = sorted(buscados - set(ok + omitidos + fallidos))
    if faltan:
        print("No aparecieron en el listado:", ", ".join(faltan))
    if args.min_kw is not None:
        clasificar(destino, args.min_kw)


if __name__ == "__main__":
    main()
