"""Buscador TE4: busca y descarga las declaraciones TE4 del e-Declarador de la SEC.

Windows: doble clic en "Iniciar Buscador TE4.bat" (la primera vez instala lo necesario).
Otros sistemas: pip install -r requirements.txt  y luego  python buscador_te4.py
"""
import csv
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from collections import Counter
from datetime import date
from tkinter import filedialog, messagebox, simpledialog, ttk

import edeclarador as sec

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre")
COLUMNAS = (  # campo, título, ancho, alineación
    ("estado", "Estado", 125, "w"),
    ("folio", "Folio", 80, "center"),
    ("fecha", "Fecha", 95, "center"),
    ("propietario", "Propietario", 230, "w"),
    ("rut_propietario", "RUT propietario", 132, "center"),
    ("direccion", "Dirección", 260, "w"),
    ("comuna", "Comuna", 120, "w"),
    ("region", "Región", 110, "w"),
    ("kw", "kW", 70, "e"),
    ("pdf", "PDF", 45, "center"),
)
CSV_CAMPOS = (("estado", "Estado"), ("folio", "Folio"), ("fecha", "Fecha"), ("fecha_estado", "Fecha último estado"),
              ("estado_sec", "Estado SEC"), ("propietario", "Propietario"), ("rut_propietario", "RUT propietario"),
              ("direccion", "Dirección"), ("comuna", "Comuna"), ("region", "Región"),
              ("kw", "Potencia Total Instalada del EG (kW)"), ("kw_declarada", "Potencia Total Declarada (kW)"),
              ("distribuidora", "Distribuidora"), ("tipo", "Tipo de declaración"))


def _fecha_larga(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _clave_orden(campo, r, tiene_pdf):
    if campo == "kw":
        return r.get("kw") or 0
    if campo == "fecha":
        f = r.get("fecha") or ""
        return f[6:10] + f[3:5] + f[:2]
    if campo == "folio":
        return int(r.get("folio") or 0)
    if campo == "pdf":
        return tiene_pdf
    return sec._normal(r.get(campo))


def _abrir(ruta):
    if sys.platform == "win32":
        os.startfile(ruta)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(ruta)])


class Buscador(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Buscador TE4 · e-Declarador SEC")
        self.geometry("1320x740")
        self.minsize(980, 520)
        self.config_sec = sec.cargar_config()
        self.datos = {"registros": []}
        self.visibles = []
        self.orden = ("fecha", True)  # columna, descendente
        self.cola = queue.Queue()
        self.detener = threading.Event()
        self.ocupado = False
        self._refresco = None
        self._armar()
        rut = self.config_sec.get("ultimo_rut", "")
        self.var_rut.set(sec.rut_con_puntos(rut) if rut else "")
        self.cargar_cuenta()
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.after(150, self._atender_cola)

    # ------------------------------------------------------------ armado de la ventana

    def _armar(self):
        estilo = ttk.Style(self)
        for tema in ("vista", "clam"):
            if tema in estilo.theme_names():
                estilo.theme_use(tema)
                break

        cuenta = ttk.LabelFrame(self, text="Cuenta e-Declarador (instalador)")
        cuenta.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(cuenta, text="RUT:").pack(side="left", padx=(8, 2), pady=6)
        self.var_rut = tk.StringVar()
        entrada_rut = ttk.Entry(cuenta, textvariable=self.var_rut, width=14)
        entrada_rut.pack(side="left")
        entrada_rut.bind("<FocusOut>", lambda _: self.cargar_cuenta())
        entrada_rut.bind("<Return>", lambda _: self.cargar_cuenta())
        ttk.Label(cuenta, text="Clave:").pack(side="left", padx=(12, 2))
        self.var_clave = tk.StringVar()
        ttk.Entry(cuenta, textvariable=self.var_clave, width=16, show="•").pack(side="left")
        self.btn_actualizar = ttk.Button(cuenta, text="Actualizar desde la SEC", command=self.actualizar)
        self.btn_actualizar.pack(side="left", padx=10)
        self.var_visible = tk.BooleanVar(value=False)
        ttk.Checkbutton(cuenta, text="Ver navegador", variable=self.var_visible).pack(side="left")
        self.lbl_actualizado = ttk.Label(cuenta, text="", foreground="#555")
        self.lbl_actualizado.pack(side="right", padx=8)

        filtros = ttk.LabelFrame(self, text="Búsqueda")
        filtros.pack(fill="x", padx=10, pady=4)
        self.var_texto, self.var_campo = tk.StringVar(), tk.StringVar(value="Todos los campos")
        self.var_estado = tk.StringVar(value="Todos")
        self.var_kw_min, self.var_kw_max = tk.StringVar(), tk.StringVar()
        ttk.Label(filtros, text="Buscar:").grid(row=0, column=0, padx=(8, 2), pady=6)
        entrada = ttk.Entry(filtros, textvariable=self.var_texto, width=40)
        entrada.grid(row=0, column=1, sticky="we")
        ttk.Label(filtros, text="en:").grid(row=0, column=2, padx=(8, 2))
        ttk.Combobox(filtros, textvariable=self.var_campo, values=list(sec.CAMPOS), state="readonly",
                     width=17).grid(row=0, column=3)
        ttk.Label(filtros, text="Estado:").grid(row=0, column=4, padx=(12, 2))
        ttk.Combobox(filtros, textvariable=self.var_estado, values=["Todos", *sec.ESTADOS], state="readonly",
                     width=15).grid(row=0, column=5)
        ttk.Label(filtros, text="kW desde:").grid(row=0, column=6, padx=(12, 2))
        ttk.Entry(filtros, textvariable=self.var_kw_min, width=7).grid(row=0, column=7)
        ttk.Label(filtros, text="hasta:").grid(row=0, column=8, padx=(6, 2))
        ttk.Entry(filtros, textvariable=self.var_kw_max, width=7).grid(row=0, column=9)
        ttk.Button(filtros, text="Limpiar", command=self.limpiar_filtros).grid(row=0, column=10, padx=8)
        filtros.columnconfigure(1, weight=1)
        for var in (self.var_texto, self.var_campo, self.var_estado, self.var_kw_min, self.var_kw_max):
            var.trace_add("write", lambda *_: self._programar_refresco())
        entrada.focus_set()

        marco = ttk.Frame(self)
        marco.pack(fill="both", expand=True, padx=10, pady=4)
        self.tree = ttk.Treeview(marco, columns=[c[0] for c in COLUMNAS], show="headings", selectmode="extended")
        for campo, titulo, ancho, alineacion in COLUMNAS:
            self.tree.heading(campo, text=titulo, command=lambda c=campo: self.ordenar(c))
            self.tree.column(campo, width=ancho, minwidth=40, anchor=alineacion,
                             stretch=campo in ("propietario", "direccion"))
        vertical = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(marco, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _: self.abrir_pdf())

        acciones = ttk.Frame(self)
        acciones.pack(fill="x", padx=10, pady=4)
        self.botones = [self.btn_actualizar]
        for texto, comando in (("Descargar PDF de seleccionados", lambda: self.descargar(False)),
                               ("Descargar PDF de toda la lista", lambda: self.descargar(True)),
                               ("Abrir PDF", self.abrir_pdf),
                               ("Abrir carpeta de PDF", self.abrir_carpeta),
                               ("Exportar listado PDF", self.exportar_listado),
                               ("Exportar a Excel (CSV)", self.exportar_csv)):
            boton = ttk.Button(acciones, text=texto, command=comando)
            boton.pack(side="left", padx=(0, 6))
            self.botones.append(boton)
        self.btn_detener = ttk.Button(acciones, text="Detener", command=self.detener.set, state="disabled")
        self.btn_detener.pack(side="right")

        pie = ttk.Frame(self)
        pie.pack(fill="x", padx=10, pady=(2, 8))
        self.lbl_resumen = ttk.Label(pie, text="")
        self.lbl_resumen.pack(side="left")
        self.barra = ttk.Progressbar(pie, length=220, mode="determinate")
        self.barra.pack(side="right")
        self.lbl_progreso = ttk.Label(pie, text="", foreground="#555")
        self.lbl_progreso.pack(side="right", padx=8)

    # ------------------------------------------------------------ datos y tabla

    def _rut(self):
        return self.var_rut.get().strip()

    def cargar_cuenta(self):
        rut = self._rut()
        self.datos = sec.cargar(rut) if sec.rut_valido(rut) else {"registros": []}
        actualizado = self.datos.get("actualizado")
        self.lbl_actualizado["text"] = (f"Última actualización: {actualizado}" if actualizado else
                                        "Sin datos: presiona «Actualizar desde la SEC»" if sec.rut_valido(rut) else "")
        self.refrescar()

    def _kw(self, var):
        texto = var.get().strip().replace(",", ".")
        try:
            return float(texto) if texto else None
        except ValueError:
            return None

    def _programar_refresco(self):
        if self._refresco:
            self.after_cancel(self._refresco)
        self._refresco = self.after(200, self.refrescar)

    def refrescar(self):
        self._refresco = None
        estado = self.var_estado.get()
        registros = sec.filtrar(self.datos["registros"], self.var_texto.get(), self.var_campo.get(),
                                None if estado == "Todos" else estado, self._kw(self.var_kw_min), self._kw(self.var_kw_max))
        rut = self._rut()
        con_pdf = {id(r) for r in registros if r["estado"] == "Inscrito" and sec.ruta_pdf(rut, r["folio"]).exists()}
        campo, descendente = self.orden
        vacios = [r for r in registros if campo != "pdf" and r.get(campo) in (None, "")]  # siempre al final
        registros = sorted((r for r in registros if campo == "pdf" or r.get(campo) not in (None, "")),
                           key=lambda r: _clave_orden(campo, r, id(r) in con_pdf), reverse=descendente) + vacios
        self.visibles = registros
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(registros):
            self.tree.insert("", "end", iid=str(i), values=(
                r["estado"], r["folio"], r.get("fecha", ""), r.get("propietario", ""), r.get("rut_propietario", ""),
                r.get("direccion", ""), r.get("comuna", ""), r.get("region", ""),
                sec.kw_cl(r["kw"]) if r.get("kw") is not None else "", "✓" if id(r) in con_pdf else ""))
        for c, titulo, *_ in COLUMNAS:
            self.tree.heading(c, text=titulo + ((" ▼" if descendente else " ▲") if c == campo else ""))
        total = sum(r["kw"] for r in registros if r.get("kw") is not None)
        inscritos = sum(r["estado"] == "Inscrito" for r in registros)
        self.lbl_resumen["text"] = (f"{len(registros)} resultados · {inscritos} inscritos · "
                                    f"{sec.kw_cl(total)} kW de Potencia Total Instalada del EG")

    def ordenar(self, campo):
        actual, descendente = self.orden
        self.orden = (campo, not descendente if actual == campo else False)
        self.refrescar()

    def limpiar_filtros(self):
        for var in (self.var_texto, self.var_kw_min, self.var_kw_max):
            var.set("")
        self.var_campo.set("Todos los campos")
        self.var_estado.set("Todos")

    def _seleccionados(self):
        return [self.visibles[int(i)] for i in self.tree.selection()]

    # ------------------------------------------------------------ tareas en segundo plano

    def _credenciales(self):
        rut, clave = self._rut(), self.var_clave.get()
        if not sec.rut_valido(rut):
            messagebox.showwarning("RUT", "Ingresa un RUT válido, por ejemplo 12.345.678-9.")
            return None
        if not clave:
            messagebox.showwarning("Clave", "Ingresa la clave del e-Declarador.")
            return None
        self.config_sec["ultimo_rut"] = sec.rut_normal(rut)
        sec.guardar_config(self.config_sec)
        return rut, clave, self.var_visible.get()

    def _en_segundo_plano(self, tarea, al_terminar):
        """Ejecuta tarea(avisar, detener) en otro hilo para que la ventana no se congele."""
        self.ocupado = True
        self.detener.clear()
        for boton in self.botones:
            boton.state(["disabled"])
        self.btn_detener.state(["!disabled"])
        self.barra.configure(value=0, maximum=1)

        def avisar(texto, i=None, n=None):
            self.cola.put(("avisar", (texto, i, n)))

        def correr():
            try:
                self.cola.put(("listo", (al_terminar, tarea(avisar, self.detener.is_set))))
            except Exception as e:  # se muestra en la ventana
                self.cola.put(("error", e))

        threading.Thread(target=correr, daemon=True).start()

    def _atender_cola(self):
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "avisar":
                    texto, i, n = dato
                    self.lbl_progreso["text"] = texto
                    if n:
                        self.barra.configure(maximum=n, value=i)
                    continue
                self.ocupado = False
                for boton in self.botones:
                    boton.state(["!disabled"])
                self.btn_detener.state(["disabled"])
                self.lbl_progreso["text"] = ""
                self.barra.configure(value=0)
                if tipo == "listo":
                    al_terminar, resultado = dato
                    al_terminar(resultado)
                else:
                    self._mostrar_error(dato)
        except queue.Empty:
            pass
        self.after(150, self._atender_cola)

    def _mostrar_error(self, error):
        if isinstance(error, sec.SinNavegador):
            if messagebox.askyesno("Navegador", f"{error}\n\n¿Descargar ahora el navegador Chromium (unos 150 MB)?"):
                self._en_segundo_plano(
                    lambda avisar, detener: (avisar("Descargando Chromium…"), subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "chromium"], check=True, capture_output=True)),
                    lambda _: messagebox.showinfo("Navegador", "Chromium instalado. Vuelve a intentarlo."))
        elif isinstance(error, sec.ErrorSEC):
            messagebox.showerror("e-Declarador SEC", str(error))
        else:
            messagebox.showerror("Error", f"{type(error).__name__}: {error}")

    def actualizar(self):
        credenciales = self._credenciales()
        if credenciales:
            rut, clave, visible = credenciales
            self._en_segundo_plano(lambda avisar, detener: sec.actualizar(rut, clave, visible, avisar, detener),
                                   self._fin_actualizar)

    def _fin_actualizar(self, datos):
        self.cargar_cuenta()
        cuenta = Counter(r["estado"] for r in datos["registros"])
        pendientes = sum(r["estado"] == "Inscrito" and r.get("kw") is None for r in datos["registros"])
        texto = "\n".join(f"{estado}: {cuenta.get(estado, 0)}" for estado in sec.ESTADOS)
        if pendientes:
            texto += f"\n\nQuedan {pendientes} certificados por leer: vuelve a actualizar para completarlos."
        messagebox.showinfo("Actualización terminada", texto)

    def descargar(self, toda_la_lista):
        registros = self.visibles if toda_la_lista else self._seleccionados()
        inscritos = [r for r in registros if r["estado"] == "Inscrito"]
        if not inscritos:
            messagebox.showinfo("Descargar PDF", "Selecciona uno o más TE4 inscritos: solo ellos tienen certificado PDF."
                                if not toda_la_lista else "La lista no tiene TE4 inscritos.")
            return
        rut = self._rut()
        folios = [r["folio"] for r in inscritos if not sec.ruta_pdf(rut, r["folio"]).exists()]
        if not folios:
            messagebox.showinfo("Descargar PDF", "Esos certificados ya están descargados.")
            return
        if len(folios) > 10 and not messagebox.askyesno(
                "Descargar PDF", f"Se descargarán {len(folios)} certificados (unos {max(1, round(len(folios) / 10))} "
                                 "minutos). ¿Continuar?"):
            return
        credenciales = self._credenciales()
        if credenciales:
            rut, clave, visible = credenciales
            self._en_segundo_plano(
                lambda avisar, detener: sec.descargar_pdfs(rut, clave, folios, visible, avisar, detener),
                self._fin_descargar)

    def _fin_descargar(self, resultado):
        hechos, errores = resultado
        self.refrescar()
        texto = f"Descargados: {len(hechos)}"
        if errores:
            texto += "\n\nCon error:\n" + "\n".join(f"{folio}: {error}" for folio, error in errores[:15])
        (messagebox.showwarning if errores else messagebox.showinfo)("Descarga terminada", texto)

    # ------------------------------------------------------------ archivos

    def abrir_pdf(self):
        seleccion = self._seleccionados()
        if not seleccion:
            return
        r = seleccion[0]
        if r["estado"] != "Inscrito":
            messagebox.showinfo("PDF", "Solo los TE4 inscritos tienen certificado PDF.")
            return
        ruta = sec.ruta_pdf(self._rut(), r["folio"])
        if ruta.exists():
            _abrir(ruta)
        elif not self.ocupado and messagebox.askyesno(
                "PDF", f"El certificado del folio {r['folio']} no está descargado. ¿Descargarlo ahora?"):
            self.descargar(False)

    def abrir_carpeta(self):
        if not sec.rut_valido(self._rut()):
            return
        carpeta = sec.carpeta_cuenta(self._rut()) / "certificados"
        carpeta.mkdir(parents=True, exist_ok=True)
        _abrir(carpeta)

    def exportar_listado(self):
        filas = [r for r in self.visibles if r["estado"] == "Inscrito" and r.get("kw") is not None]
        if not filas:
            messagebox.showinfo("Listado PDF", "La lista no tiene TE4 inscritos con su potencia leída.")
            return
        try:
            import listado_pdf
        except ImportError:
            messagebox.showerror("Listado PDF", "Falta reportlab. Instálalo con: pip install -r requirements.txt")
            return
        rut = sec.rut_normal(self._rut())
        nombres = self.config_sec.setdefault("nombres_listado", {})
        frecuentes = Counter(r["instalador"].title() for r in self.datos["registros"] if r.get("instalador"))
        sugerido = nombres.get(rut) or (frecuentes.most_common(1)[0][0] if frecuentes else self.datos.get("instalador", ""))
        nombre = simpledialog.askstring("Listado PDF", "Nombre del instalador para el listado:", initialvalue=sugerido,
                                        parent=self)
        if not nombre or not nombre.strip():
            return
        ruta = filedialog.asksaveasfilename(title="Guardar listado PDF", defaultextension=".pdf",
                                            filetypes=[("PDF", "*.pdf")],
                                            initialfile=f"Listado_TE4_{date.today():%d-%m-%Y}.pdf")
        if not ruta:
            return
        nombres[rut] = nombre.strip()
        sec.guardar_config(self.config_sec)
        hoy, kw_min = _fecha_larga(date.today()), self._kw(self.var_kw_min)
        if kw_min is not None:
            subtitulo = ("Instalaciones con Potencia Total Instalada del EG igual o superior a "
                         f"{kw_min:g}".replace(".", ",") + " kW")
        elif self.var_texto.get().strip() or self._kw(self.var_kw_max) is not None:
            subtitulo = f"Selección de declaraciones inscritas al {hoy}"
        else:
            subtitulo = f"Listado completo de declaraciones inscritas al {hoy}"
        filas.sort(key=lambda r: (_clave_orden("fecha", r, False), int(r["folio"])))
        try:
            listado_pdf.generar(ruta, [(r["folio"], r.get("fecha", ""), r["kw"]) for r in filas], nombre.strip(),
                                sec.rut_con_puntos(rut), subtitulo, hoy)
        except PermissionError:
            messagebox.showerror("Listado PDF", "No se pudo guardar: ¿el archivo está abierto en otro programa?")
            return
        total = sec.kw_cl(sum(r["kw"] for r in filas))
        if messagebox.askyesno("Listado PDF", f"Listado guardado: {len(filas)} TE4, {total} kW.\n\n¿Abrirlo?"):
            _abrir(ruta)

    def exportar_csv(self):
        if not self.visibles:
            messagebox.showinfo("Exportar", "La lista está vacía.")
            return
        ruta = filedialog.asksaveasfilename(title="Exportar a Excel (CSV)", defaultextension=".csv",
                                            filetypes=[("CSV para Excel", "*.csv")],
                                            initialfile=f"TE4_{date.today():%d-%m-%Y}.csv")
        if not ruta:
            return
        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:  # con BOM: Excel respeta las tildes
                escritor = csv.writer(archivo, delimiter=";")
                escritor.writerow([titulo for _, titulo in CSV_CAMPOS])
                for r in self.visibles:
                    escritor.writerow([f"{r[c]:g}".replace(".", ",") if c.startswith("kw") and r.get(c) is not None
                                       else r.get(c, "") for c, _ in CSV_CAMPOS])
        except PermissionError:
            messagebox.showerror("Exportar", "No se pudo guardar: ¿el archivo está abierto en Excel?")
            return
        messagebox.showinfo("Exportar", f"Se exportaron {len(self.visibles)} filas.")

    def cerrar(self):
        if self.ocupado and not messagebox.askyesno("Salir", "Hay una tarea en curso. ¿Salir de todas formas?"):
            return
        self.destroy()


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # texto nítido en pantallas de alta resolución
        except (AttributeError, OSError):
            pass
    Buscador().mainloop()


if __name__ == "__main__":
    main()
