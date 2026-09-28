"""Conexión con el e-Declarador TE4 de la SEC y base local de declaraciones.

Lo usa buscador_te4.py (la ventana); también se puede importar desde otros scripts. En la SEC solo
lee: listados, bandejas y la ventana del certificado ("Imprimir" para el PDF). Nunca corrige, firma
ni crea presentaciones.
"""
import json
import logging
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import Error as PWError, TimeoutError as PWTimeout, sync_playwright
except ImportError:  # la ventana abre igual; avisa al intentar conectarse
    sync_playwright = None
    PWError = PWTimeout = RuntimeError

BASE = "https://wlhttp.sec.cl/edeclaradorTE4/"
URL_LOGIN = BASE + "declarador.jsp"
URL_CERTIFICADO = BASE + "usuarioDeclarador.do?accion=verInscripcionPopUp&folioPresentacion={}"
DATOS = Path(__file__).resolve().parent / "datos"
BANDEJAS = {  # estado -> opción del menú "Bandeja de Entrada"
    "En revisión": "menu.usuarioDeclarador.bandejaEntrada.enRevision",
    "Por corregir": "menu.usuarioDeclarador.bandejaEntrada.porCorregir",
    "En construcción": "menu.usuarioDeclarador.bandejaEntrada.enConstruccion",
}
ESTADOS = ("Inscrito", *BANDEJAS)
RUT = r"\d{1,2}(?:\.?\d{3}){2}-[\dkK]"
logging.getLogger("pypdf").setLevel(logging.ERROR)  # avisos internos de PDF que no afectan la lectura
JSID = re.compile(r";jsessionid=[^?#]*", re.I)
ES_TE4 = re.compile(r"\bTE-?4\b", re.I)

# Filas de la grilla que tiene la columna `cabecera`, como {columna: texto}, y la paginación.
JS_GRILLA = r"""(cabecera) => {
  const norm = s => (s || "").replace(/\s+/g, " ").trim();
  const pag = norm(document.body.innerText).match(/P[aá]gina\s*(\d+)\s*de\s*(\d+)/i);
  for (const t of document.querySelectorAll("table")) {
    const filas = Array.from(t.rows);
    const h = filas.findIndex(r => r.cells.length >= 4 && Array.from(r.cells).some(c => norm(c.innerText) === cabecera));
    if (h < 0) continue;
    const cols = Array.from(filas[h].cells).map(c => norm(c.innerText));
    return {pagina: pag ? +pag[1] : 1, paginas: pag ? +pag[2] : 1,
            filas: filas.slice(h + 1).filter(r => r.cells.length === cols.length)
                        .map(r => Object.fromEntries(cols.map((c, i) => [c, norm(r.cells[i].innerText)])))};
  }
  return {pagina: 1, paginas: 1, filas: []};
}"""

# Marca el enlace a la página siguiente del listado (número de página o flecha "adelante").
JS_SIGUIENTE = r"""(pagina) => {
  const norm = s => (s || "").replace(/\s+/g, " ").trim();
  const links = Array.from(document.querySelectorAll("a"));
  const el = links.find(a => norm(a.innerText) === String(pagina + 1)) ||
             links.find(a => a.querySelector("img[src*='adelante'], img[src*='siguiente']"));
  if (!el) return false;
  el.setAttribute("data-te4-sig", "");
  return true;
}"""


class ErrorSEC(Exception):
    """Error con un mensaje para mostrar tal cual al usuario."""


class SinNavegador(ErrorSEC):
    pass


class SesionSEC:
    """Sesión iniciada en el e-Declarador.  with SesionSEC(rut, clave) as s: s.inscritos() ..."""

    def __init__(self, rut, clave, visible=False):
        self.rut, self.clave, self.visible = rut, clave, visible
        self.nombre = ""
        self.alertas = []

    def __enter__(self):
        if sync_playwright is None:
            raise ErrorSEC("Falta Playwright. Instálalo con: pip install -r requirements.txt")
        self._pw = sync_playwright().start()
        self._navegador = None
        try:
            self._navegador = _abrir_navegador(self._pw, self.visible)
            self.ctx = self._navegador.new_context()
            # la sesión viaja en la cookie; algunos proxies y firewalls rechazan ";jsessionid=" en la URL
            self.ctx.route(re.compile(r";jsessionid=", re.I), lambda r: r.continue_(url=JSID.sub("", r.request.url)))
            self.ctx.on("page", lambda p: p.on("dialog", self._dialogo))
            self.page = self.ctx.new_page()
            self._ingresar()
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *exc):
        try:
            if self._navegador:
                self._navegador.close()
        finally:
            self._pw.stop()

    def _dialogo(self, dialogo):
        self.alertas.append(dialogo.message)
        dialogo.accept()

    def _ir(self, js, arg=None):
        """Ejecuta una acción del sitio que carga otra página y espera a que termine."""
        with self.page.expect_navigation(timeout=120000):
            self.page.evaluate(js, arg)

    def _ingresar(self):
        p = self.page
        p.goto(URL_LOGIN, timeout=90000)
        p.fill("input[name=declaRut]", self.rut)
        p.fill("input[name=password]", self.clave)
        self.alertas.clear()
        try:
            with p.expect_navigation(timeout=90000):
                p.evaluate("() => enviarForm('ingresar_usuario')")  # lo mismo que el botón INGRESAR
                if self.alertas:  # la página rechazó el RUT antes de enviarlo
                    raise ErrorSEC("No se pudo iniciar sesión: " + " ".join(dict.fromkeys(self.alertas)))
        except PWTimeout:
            pass
        texto = p.inner_text("body")
        if p.locator("input[name=declaRut]").count():
            motivos = [l.strip() for l in texto.splitlines()
                       if re.search(r"incorrect|inv[aá]lid|bloque|no existe|expir|error", l, re.I)]
            raise ErrorSEC("No se pudo iniciar sesión" + (": " + " ".join(motivos + self.alertas) if motivos or self.alertas
                                                          else ". Revisa el RUT y la clave."))
        m = re.search(r"([^\n]+?)\s*\n\s*" + RUT + r"\s*\n\s*Perfil", texto)
        self.nombre = m.group(1).strip().title() if m else ""

    def _grilla(self, cabecera):
        """Filas de todas las páginas del listado que se está viendo."""
        filas, vistas = [], set()
        while True:
            r = self.page.evaluate(JS_GRILLA, cabecera)
            firma = tuple(f.get(cabecera, "") for f in r["filas"])
            if firma in vistas:
                break
            vistas.add(firma)
            filas += r["filas"]
            if r["pagina"] >= r["paginas"] or not self.page.evaluate(JS_SIGUIENTE, r["pagina"]):
                break
            with self.page.expect_navigation(timeout=120000):
                self.page.click("[data-te4-sig]")
        return filas

    def inscritos(self):
        """TE4 inscritos según el listado (folio y fecha; el resto sale de cada certificado)."""
        self._ir("a => enviarForm(a)", "menu.usuarioDeclarador.declaracionesInscritas")
        self.page.evaluate(r"""() => { const s = document.querySelector("select[name=tipoTramiteINP]");
            if (s) for (const o of s.options) if (/\bTE-?4\b/i.test(o.text)) s.value = o.value; }""")
        self._ir("() => enviarForm2('menu.usuarioDeclarador.declaracionesInscritas', "
                 "'menu.usuarioDeclarador.declaracionesInscritas.buscar')")
        return [{"estado": "Inscrito", "folio": _digitos(f.get("Folio Inscripción")), "tramite": "TE4",
                 "fecha": f.get("Fecha de Inscripción", "")}
                for f in self._grilla("Folio Inscripción") if ES_TE4.search(f.get("Tipo Trámite", ""))]

    def bandeja(self, estado):
        """Presentaciones TE4 de una bandeja ("En revisión", "Por corregir" o "En construcción")."""
        self._ir("a => enviarForm(a)", BANDEJAS[estado])
        registros = []
        for f in self._grilla("Folio Presentación"):
            if not ES_TE4.search(f.get("Tipo de Trámite", "")):
                continue
            rut, nombre = _separar_propietario(f.get("Propietario Instalación", ""))
            direccion, comuna, region = _separar_direccion(f.get("Dirección Instalación", ""))
            registros.append({"estado": estado, "folio": _digitos(f.get("Folio Presentación")), "tramite": "TE4",
                              "fecha": f.get("Fecha Presentación", ""), "fecha_estado": f.get("Fecha Último Estado", ""),
                              "estado_sec": f.get("Estado") or f.get("Origen Presentación", ""),
                              "propietario": nombre, "rut_propietario": rut,
                              "direccion": direccion, "comuna": comuna, "region": region})
        return registros

    def _abrir_certificado(self, folio):
        p = self.ctx.new_page()
        try:
            p.goto(URL_CERTIFICADO.format(folio), timeout=120000)
            p.wait_for_selector("text=Potencia Total", timeout=120000)
        except BaseException:
            p.close()
            raise
        return p

    def certificado(self, folio):
        """Datos del certificado de un TE4 inscrito (propietario, dirección, potencia, etc.)."""
        p = self._abrir_certificado(folio)
        try:
            return leer_certificado(p.inner_text("body"))
        finally:
            p.close()

    def descargar_pdf(self, folio, ruta):
        """Guarda en `ruta` el PDF oficial del certificado (el que entrega su botón "Imprimir")."""
        pdfs = []

        def capturar(route):
            if route.request.resource_type not in ("document", "xhr", "fetch", "other"):
                return route.fallback()
            try:
                respuesta = route.fetch()
                cuerpo = respuesta.body()
            except PWError:
                return route.fallback()
            inicio = cuerpo.find(b"%PDF", 0, 1024)
            if inicio < 0:
                return route.fulfill(response=respuesta)
            pdfs.append(cuerpo[inicio:])
            route.fulfill(status=204)  # sin visor ni descarga: el PDF ya quedó guardado aquí

        p = self._abrir_certificado(folio)
        try:
            p.route("**/*", capturar)
            try:
                p.evaluate("() => enviar('DESPLPDF')")  # botón "Imprimir" de la ventana del certificado
            except PWError:
                pass  # la navegación puede cortar el evaluate
            fin = time.time() + 120
            while not pdfs and time.time() < fin:
                p.wait_for_timeout(250)
        finally:
            p.close()
        if not pdfs:
            raise ErrorSEC(f"La SEC no entregó el PDF del folio {folio}.")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(pdfs[0])


def _abrir_navegador(pw, visible):
    """Microsoft Edge o Google Chrome instalados en el PC; si no hay, el Chromium de Playwright."""
    errores = []
    for canal in ("msedge", "chrome", None):
        try:
            return pw.chromium.launch(channel=canal, headless=not visible)
        except PWError as e:
            errores.append(f"{canal or 'chromium'}: {str(e).strip().splitlines()[0]}")
    raise SinNavegador("No encontré Microsoft Edge ni Google Chrome.\n" + "\n".join(errores))


# ---------------------------------------------------------------- lectura de textos del sitio

def _digitos(texto):
    return re.sub(r"\D", "", texto or "")


def _limpio(texto):
    """Quita los rótulos vacíos que la SEC deja en las direcciones ("Depto. Block")."""
    s = re.sub(r"\s+", " ", texto or "")
    s = re.sub(r"\s*\bDepto\.?\s*Block\b", "", s)
    s = re.sub(r"\s+Block\s*$", "", s)
    s = re.sub(r"\s*\bDepto\.?\s*$", "", s)
    return s.strip(" ,:-")


def _separar_propietario(texto):
    """'7.430.371-4 Luis Pérez' -> ('7.430.371-4', 'Luis Pérez')."""
    m = re.match(r"\s*(" + RUT + r")\s*(.*)", texto or "")
    if m:
        return m.group(1).upper(), _limpio(m.group(2))
    return "", ("" if (texto or "").strip() in ("", "-") else _limpio(texto))


def _separar_direccion(texto):
    """'Calle 123 , Comuna, Región' -> ('Calle 123', 'Comuna', 'Región')."""
    partes = [_limpio(p) for p in (texto or "").split(",")]
    partes = [p for p in partes if p]
    if len(partes) >= 3:
        return ", ".join(partes[:-2]), partes[-2], partes[-1]
    return ", ".join(partes), "", ""


def _direccion_antigua(texto):
    """Certificados antiguos: 'Calle 1 Depto. Block Comuna / Región' (PDF) o 'Calle 1 , Comuna , Región' (ventana)."""
    izq, barra, region = texto.rpartition(" / ")  # con espacios, para no partir un "S/N"
    m = re.match(r"(.*)\bBlock\b(.*)$", izq) if barra else None
    if m:
        return _limpio(m.group(1)), _limpio(m.group(2)), _limpio(region)
    return _separar_direccion(texto)


def leer_certificado(texto):
    """Datos de un certificado TE4, desde el texto de su ventana en el e-Declarador o de su PDF."""
    t = re.sub(r"\s+", " ", texto or "")
    d = {}
    if m := re.search(r"FOLIO INSCRIPCION\s*0*(\d+)", t, re.I):
        d["folio"] = m.group(1)
    if m := re.search(r"Fecha y Hora Inscripci[oó]n\s*:?\s*(\d{2}/\d{2}/\d{4})", t, re.I):
        d["fecha"] = m.group(1)
    if m := re.search(r"Antecedentes de(?:l)? Instalador.*?Nombre Completo\s*:?\s*(.*?)\s*\bRUT\b\s*:?\s*(" + RUT + ")",
                      t, re.I):
        d["instalador"], d["rut_instalador"] = _limpio(m.group(1)), m.group(2).upper()
    propietario = r"Propietario\s*\(\s*Particular o Empresa\s*\)\s*Nombre Completo\s*:?\s*(.*?)\s*"
    if m := re.search(propietario + r"\bRUT\b\s*:?\s*(" + RUT + ")", t, re.I):
        d["propietario"], d["rut_propietario"] = _limpio(m.group(1)), m.group(2).upper()
    elif m := re.search(propietario + r"(?:\bRUT\b|Domicilio)", t, re.I):
        d["propietario"] = _limpio(m.group(1))
    if m := re.search(r"Regi[oó]n\s*/\s*Comuna\s*:?\s*(.+?)\s*/\s*(.+?)\s+Direcci[oó]n\s*:?\s*(.+?)\s+Declara Instalaci", t, re.I):
        d["region"], d["comuna"], d["direccion"] = _limpio(m.group(1)), _limpio(m.group(2)), _limpio(m.group(3))
    elif m := re.search(r"Direcci[oó]n\s*:?\s*((?:(?!Direcci[oó]n).)+?)\s+Declara Instalaci", t, re.I):
        d["direccion"], d["comuna"], d["region"] = _direccion_antigua(m.group(1))
    for campo, rotulo in (("kw", r"Potencia Total Instalada del EG"), ("kw_declarada", r"Potencia Total Declarada")):
        if m := re.search(rotulo + r"\s*\(kW\)\s*(\d+(?:[.,]\d+)?)", t, re.I):
            d[campo] = float(m.group(1).replace(",", "."))
    if m := re.search(r"Empresa Distribuidora\s*:?\s*(.+?)\s+(?:In Protecci|Capacidad del Empalme|Nivel de Tensi)", t, re.I):
        d["distribuidora"] = _limpio(m.group(1))
    if m := re.search(r"Tipo de Declaraci[oó]n\s*:?\s*([A-Za-zÁÉÍÓÚáéíóú]+)", t):
        d["tipo"] = m.group(1).capitalize()
    elif m := re.search(r"Generadoras Residenciales\s*-\s*(.+?)\s+Superintendencia", t, re.I):
        d["tipo"] = m.group(1).strip()
    return d


def leer_pdf(ruta):
    """Datos de un certificado TE4 guardado en PDF."""
    from pypdf import PdfReader
    return leer_certificado(" ".join(p.extract_text() or "" for p in PdfReader(ruta).pages))


# ---------------------------------------------------------------- RUT, base local y búsqueda

def rut_normal(rut):
    """'16.764.504-6' -> '16764504-6'."""
    s = re.sub(r"[^0-9kK]", "", rut or "").upper()
    return f"{s[:-1]}-{s[-1]}" if len(s) > 1 else s


def rut_valido(rut):
    cuerpo, _, dv = rut_normal(rut).partition("-")
    if not cuerpo.isdigit() or not dv:
        return False
    suma = sum(int(c) * (2 + i % 6) for i, c in enumerate(reversed(cuerpo)))
    return dv == {10: "K", 11: "0"}.get(11 - suma % 11, str(11 - suma % 11))


def rut_con_puntos(rut):
    cuerpo, _, dv = rut_normal(rut).partition("-")
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}" if cuerpo.isdigit() else rut


def carpeta_cuenta(rut):
    return DATOS / rut_normal(rut)


def ruta_pdf(rut, folio):
    return carpeta_cuenta(rut) / "certificados" / f"TE4_{folio}.pdf"


def cargar(rut):
    archivo = carpeta_cuenta(rut) / "declaraciones.json"
    if archivo.exists():
        return json.loads(archivo.read_text(encoding="utf-8"))
    return {"rut": rut_normal(rut), "instalador": "", "actualizado": None, "registros": []}


def guardar(datos):
    carpeta = carpeta_cuenta(datos["rut"])
    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = carpeta / "declaraciones.json.tmp"
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(carpeta / "declaraciones.json")


def cargar_config():
    archivo = DATOS / "config.json"
    return json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}


def guardar_config(config):
    DATOS.mkdir(parents=True, exist_ok=True)
    (DATOS / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")


def actualizar(rut, clave, visible=False, avisar=lambda texto, i=None, n=None: None, detener=lambda: False):
    """Trae de la SEC los TE4 inscritos (con los datos de su certificado) y las bandejas, y los guarda.

    Los certificados ya leídos en una actualización anterior no se vuelven a abrir.
    """
    datos = cargar(rut)
    conocidos = {r["folio"]: r for r in datos["registros"] if r["estado"] == "Inscrito" and r.get("kw") is not None}
    with SesionSEC(rut, clave, visible) as s:
        avisar("Leyendo declaraciones inscritas…")
        inscritos = s.inscritos()
        for r in inscritos:
            r.update({k: v for k, v in conocidos.get(r["folio"], {}).items() if k not in r})
        bandejas = []
        for estado in BANDEJAS:
            avisar(f"Leyendo bandeja «{estado}»…")
            bandejas += s.bandeja(estado)
        datos.update(instalador=s.nombre or datos.get("instalador", ""), registros=inscritos + bandejas)
        guardar(datos)
        pendientes = [r for r in inscritos if r.get("kw") is None]
        fallas = 0
        for i, r in enumerate(pendientes, 1):
            if detener():
                break
            avisar(f"Leyendo certificado del folio {r['folio']} ({i} de {len(pendientes)})…", i, len(pendientes))
            try:
                r.update({k: v for k, v in s.certificado(r["folio"]).items() if v not in (None, "")})
                fallas = 0
            except (PWError, ErrorSEC) as e:
                avisar(f"No se pudo leer el certificado del folio {r['folio']}: {str(e).splitlines()[0]}")
                fallas += 1
                if fallas == 3:
                    guardar(datos)
                    raise ErrorSEC("La SEC dejó de responder o cerró la sesión. Lo leído quedó guardado: "
                                   "vuelve a actualizar para continuar.")
            if i % 10 == 0:
                guardar(datos)
        # algunos certificados antiguos traen la comuna y la región solo en el PDF, no en la ventana
        sin_comuna = [r for r in inscritos if r.get("kw") is not None and not r.get("comuna")]
        for i, r in enumerate(sin_comuna, 1):
            if detener():
                break
            ruta = ruta_pdf(rut, r["folio"])
            try:
                if not ruta.exists():
                    avisar(f"Leyendo la comuna desde el PDF del folio {r['folio']} ({i} de {len(sin_comuna)})…",
                           i, len(sin_comuna))
                    s.descargar_pdf(r["folio"], ruta)
                r.update({k: v for k, v in leer_pdf(ruta).items() if k in ("comuna", "region") and v})
            except (PWError, ErrorSEC, OSError) as e:
                avisar(f"No se pudo leer el PDF del folio {r['folio']}: {str(e).splitlines()[0]}")
    datos["actualizado"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    guardar(datos)
    return datos


def descargar_pdfs(rut, clave, folios, visible=False, avisar=lambda texto, i=None, n=None: None, detener=lambda: False):
    """Descarga los certificados PDF de los folios indicados. Devuelve (descargados, [(folio, error)])."""
    hechos, errores, seguidas = [], [], 0
    with SesionSEC(rut, clave, visible) as s:
        for i, folio in enumerate(folios, 1):
            if detener():
                break
            avisar(f"Descargando TE4_{folio}.pdf ({i} de {len(folios)})…", i, len(folios))
            try:
                s.descargar_pdf(folio, ruta_pdf(rut, folio))
                hechos.append(folio)
                seguidas = 0
            except (PWError, ErrorSEC) as e:
                errores.append((folio, str(e).splitlines()[0]))
                seguidas += 1
                if seguidas == 3:
                    errores.append(("—", "La SEC dejó de responder o cerró la sesión; se detuvo la descarga."))
                    break
    return hechos, errores


def _normal(texto):
    s = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


CAMPOS = {
    "Todos los campos": ("folio", "propietario", "rut_propietario", "direccion", "comuna", "region",
                         "distribuidora", "fecha", "tipo", "estado_sec"),
    "Folio": ("folio",),
    "Propietario": ("propietario",),
    "RUT propietario": ("rut_propietario",),
    "Dirección": ("direccion",),
    "Comuna": ("comuna",),
    "Región": ("region",),
}


def filtrar(registros, texto="", campo="Todos los campos", estado=None, kw_min=None, kw_max=None):
    """Registros que cumplen todos los filtros. Cada palabra del texto debe aparecer (sin importar
    mayúsculas ni tildes); los RUT y folios se encuentran con o sin puntos y guion."""
    palabras = _normal(texto).split()
    campos = CAMPOS.get(campo, CAMPOS["Todos los campos"])
    salida = []
    for r in registros:
        if estado and r["estado"] != estado:
            continue
        kw = r.get("kw")
        if (kw_min is not None or kw_max is not None) and kw is None:
            continue
        if (kw_min is not None and kw < kw_min) or (kw_max is not None and kw > kw_max):
            continue
        if palabras:
            texto_r = " ".join(_normal(r.get(c)) for c in campos)
            compacto = re.sub(r"[\s.\-]", "", texto_r)
            if not all(p in texto_r or (any(c.isdigit() for c in p) and re.sub(r"[.\-]", "", p) in compacto)
                       for p in palabras):
                continue
        salida.append(r)
    return salida


def kw_cl(valor):
    """1234.5 -> '1.234,50'."""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
