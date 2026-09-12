"""Agregacion limitada por difusion: la forma que nadie sabe predecir.

Una particula parte lejos y camina al azar. Si toca el cumulo, se pega ahi
para siempre y sale la siguiente. Eso es todo el algoritmo -- no hay fuerzas,
no hay ecuacion de movimiento, solo azar y una regla de contacto.

De esa regla de dos lineas sale una estructura ramificada que no es azarosa en
absoluto. Su masa dentro de un radio r cumple

    N(r) ~ r^D     con D ~ 1.71 en el plano

y ese D no tiene forma cerrada: se mide, no se deduce. Cuarenta y tantos anos
despues de Witten y Sander (1981) sigue sin haber una derivacion. Aca se mide
sobre el cumulo que se acaba de generar y el numero que aparece en pantalla es
el ajuste real, no un valor de manual.

Por que ramifica: una punta que sobresale intercepta a los caminantes antes de
que lleguen al fondo de un hueco, asi que crece mas rapido y sobresale mas.
Es inestabilidad de Mullins-Sekerka, la misma que hace los copos de nieve.

Esta escena es PROBABILISTICA, que es el unico tipo de expresion que el canal
no habia tocado: todo lo demas son EDOs, EDPs, mapas iterados o construcciones
geometricas, y todos son deterministas.

Implementacion: los caminantes avanzan en paralelo con numpy y saltan usando
la transformada de distancia del espacio libre (si el cumulo mas cercano esta
a d pixeles, el paso puede ser de d-1 sin riesgo de atravesar nada). Sin ese
salto, cruzar el vacio a pasos de 1 pixel domina todo el costo.

    python scenes/dla.py -- --frames 900 --res 1920 --name shorts_dla --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_dla")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
NPART = int(arg("--n", 60000))          # particulas del cumulo
GRID = int(arg("--grid", 1700))         # lado de la grilla de crecimiento
NWALK = int(arg("--walkers", 64))       # caminantes en paralelo
REBUILD = int(arg("--rebuild", 48))     # pegados entre refrescos de la EDT
HOLD = int(arg("--hold", 70))           # frames finales con el cumulo entero
BIRTH_K = float(arg("--birth-k", 1.35))   # radio de lanzamiento = k*rmax + b
BIRTH_B = float(arg("--birth-b", 25.0))
NEARZONE = float(arg("--nearzone", 6.0))  # radio donde el paso es unitario
NOJUMP = "--nojump" in argv         # paso unitario: DLA de manual, para control
SEED = int(arg("--seed", 11))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

if FMT == "9:16":
    H, W = RES, int(round(RES * 9 / 16))
else:
    W, H = RES, int(round(RES * 9 / 16))
W -= W % 2
H -= H % 2

OLD = np.array([1.00, 0.63, 0.16])      # lo que se pego primero
NEW = np.array([0.42, 0.90, 1.00])      # la punta que esta creciendo ahora

rng = np.random.default_rng(SEED)


def grow(n_target):
    """Devuelve las posiciones en orden de pegado y el radio final.

    Dos cosas que hay que hacer bien o no crece nada:

    - la EDT se refresca cada `since >= cada` pegados, y `cada` escala con el
      tamano del cumulo. Con un intervalo fijo de 150, el cumulo de 9
      particulas nunca lo alcanza: el campo sigue viendo solo la semilla, los
      caminantes solo se pueden pegar a 1.6 px del centro, esas celdas ya
      estan ocupadas y el crecimiento se traba para siempre.
    - la cantidad de caminantes simultaneos crece con el cumulo. Mil
      caminantes alrededor de una semilla de una celda no es DLA: se pegan
      varios por tick sin verse entre si y la estadistica se deforma justo
      donde mas importa, en el nucleo.
    """
    c = GRID // 2
    occ = np.zeros((GRID, GRID), dtype=bool)
    occ[c, c] = True
    pts = [(0.0, 0.0)]
    rmax = 1.0

    edt = distance_transform_edt(~occ)
    recent = np.zeros((0, 2))          # pegados despues del ultimo refresco
    ticks = 0

    def launch(k, rb):
        a = rng.uniform(0, 2 * np.pi, k)
        return c + rb * np.cos(a), c + rb * np.sin(a)

    wx, wy = launch(NWALK, BIRTH_K * rmax + BIRTH_B)

    while len(pts) < n_target:
        ticks += 1
        nw = int(np.clip(len(pts) // 4, 24, NWALK))     # caminantes activos
        r_birth = BIRTH_K * rmax + BIRTH_B
        r_kill = min(2.2 * r_birth + 60.0, GRID / 2.0 - 6.0)

        x, y = wx[:nw], wy[:nw]
        rw = np.hypot(x - c, y - c)
        far = rw > r_kill
        if far.any():
            nf = int(far.sum())
            x[far], y[far] = launch(nf, r_birth)
            rw[far] = r_birth

        ix = np.clip(x.astype(np.int64), 1, GRID - 2)
        iy = np.clip(y.astype(np.int64), 1, GRID - 2)
        # La EDT solo conoce el cumulo del ultimo refresco. Los pegados
        # posteriores se llevan aparte y se miden exacto: sin esto el salto
        # atraviesa las puntas recien crecidas, que es justo donde vive el
        # apantallamiento, y el cumulo sale compacto (D ~ 1.95 en vez de 1.71).
        d = edt[iy, ix]
        if len(recent):
            dr = np.sqrt(((x[:, None] - recent[None, :, 0]) ** 2
                          + (y[:, None] - recent[None, :, 1]) ** 2).min(axis=1))
            d = np.minimum(d, dr)

        # Pegado EXACTO por vecindad, no por la EDT. La EDT mide de centro de
        # celda a centro de celda, asi que se equivoca hasta en 0.71 px: sobre
        # un umbral de 1.6 px eso es un 40% y hace que los caminantes se
        # peguen antes de tiempo. Medido: con la EDT como criterio, D = 1.65;
        # con la vecindad exacta, D = 1.71 como corresponde.
        cand = np.flatnonzero(d <= 2.5)
        hit = []
        if len(cand):
            cx_, cy_ = ix[cand], iy[cand]
            nb = np.zeros(len(cand), dtype=bool)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx or dy:
                        nb |= occ[cy_ + dy, cx_ + dx]
            hit = cand[nb & ~occ[cy_, cx_]]
        for k in hit:
            jx, jy = int(ix[k]), int(iy[k])
            if occ[jy, jx]:
                continue
            occ[jy, jx] = True
            pts.append((jx - c, jy - c))
            rmax = max(rmax, float(np.hypot(jx - c, jy - c)))
            recent = np.vstack([recent, [[jx + 0.5, jy + 0.5]]])
            nxx, nyy = launch(1, BIRTH_K * rmax + BIRTH_B)
            x[k], y[k] = float(nxx[0]), float(nyy[0])
            if len(pts) >= n_target:
                break

        # Salto: la distancia libre ENTERA menos un margen. Acotarlo (probe
        # con 55 px) rompe el algoritmo: en campo lejano el caminante avanza
        # de a pasitos, se pasa del radio de muerte y nunca llega al cumulo.
        # Cerca del cumulo, paso unitario: ahi el salto no ahorra casi nada y
        # el error de celda de la EDT si sesga el resultado. El salto queda
        # para el campo lejano, que es donde esta todo el costo.
        step = (np.ones_like(d) if NOJUMP
                else np.where(d <= NEARZONE, 1.0, d - 2.0))
        a = rng.uniform(0, 2 * np.pi, nw)
        wx[:nw] = x + step * np.cos(a)
        wy[:nw] = y + step * np.sin(a)

        if len(recent) >= REBUILD:
            edt = distance_transform_edt(~occ)
            recent = np.zeros((0, 2))

        if ticks % 20000 == 0:
            print(f"[dla] {len(pts)}/{n_target}  radio {rmax:.0f}  "
                  f"caminantes {nw}  ticks {ticks}", flush=True)

    print(f"[dla] {ticks} ticks para {len(pts)} particulas", flush=True)
    return np.array(pts, dtype=np.float64), rmax


def dimension_gyration(pts):
    """D del escaleo del radio de giro: R_g(n) ~ n^(1/D).

    Usa toda la historia de crecimiento en vez de un solo cumulo final, asi
    que no depende de elegir una ventana de radios y es el estimador que se
    reporta habitualmente para DLA.
    """
    ns = np.unique(np.geomspace(200, len(pts), 40).astype(int))
    rg = []
    for n in ns:
        q = pts[:n]
        cm = q.mean(axis=0)
        rg.append(np.sqrt(np.mean(np.sum((q - cm) ** 2, axis=1))))
    rg = np.array(rg)
    a, b = np.polyfit(np.log(ns), np.log(rg), 1)
    res = np.log(rg) - (a * np.log(ns) + b)
    r2 = 1.0 - np.sum(res ** 2) / np.sum((np.log(rg) - np.log(rg).mean()) ** 2)
    return float(1.0 / a), float(r2)


def fractal_dimension(pts, rmax):
    """Ajusta N(r) ~ r^D sobre la ley masa-radio, en la zona de escala."""
    r = np.hypot(pts[:, 0], pts[:, 1])
    rs = np.geomspace(0.06 * rmax, 0.62 * rmax, 26)   # ni el nucleo ni el borde
    ns = np.array([(r <= x).sum() for x in rs], dtype=float)
    ok = ns > 0
    D, b = np.polyfit(np.log(rs[ok]), np.log(ns[ok]), 1)
    res = np.log(ns[ok]) - (D * np.log(rs[ok]) + b)
    r2 = 1.0 - np.sum(res ** 2) / np.sum((np.log(ns[ok]) - np.log(ns[ok]).mean()) ** 2)
    return float(D), float(r2)


def splat(acc, x, y, col):
    ok = (x >= 0) & (x < W - 1) & (y >= 0) & (y < H - 1)
    x, y, col = x[ok], y[ok], col[ok]
    if not len(x):
        return
    ix, iy = x.astype(np.int64), y.astype(np.int64)
    fx, fy = x - ix, y - iy
    base = iy * W + ix
    flat = acc.reshape(-1, 3)
    for off, wt in ((0, (1 - fx) * (1 - fy)), (1, fx * (1 - fy)),
                    (W, (1 - fx) * fy), (W + 1, fx * fy)):
        for ch in range(3):
            flat[:, ch] += np.bincount(base + off, weights=wt * col[:, ch],
                                       minlength=flat.shape[0])


def main():
    # El cumulo se cachea: crecerlo cuesta minutos y el render se retoca
    # muchas veces. Si cambia el algoritmo, borrar cluster.npy.
    cache = os.path.join(REPO, "output", NAME, "cluster.npy")
    if os.path.isfile(cache):
        pts = np.load(cache)
        rmax = float(np.hypot(pts[:, 0], pts[:, 1]).max())
        print(f"[dla] cumulo cacheado: {len(pts)} particulas, radio {rmax:.0f}")
    else:
        print(f"[dla] creciendo {NPART} particulas en grilla {GRID}x{GRID}...")
        pts, rmax = grow(NPART)
        np.save(cache, pts)
    D, r2 = fractal_dimension(pts, rmax)
    Dg, r2g = dimension_gyration(pts)
    print(f"[dla] listo: {len(pts)} particulas, radio {rmax:.0f} px")
    print(f"[dla] D por masa-radio  = {D:.3f}  (R^2 = {r2:.4f})")
    print(f"[dla] D por radio de giro = {Dg:.3f}  (R^2 = {r2g:.4f})")

    order = np.arange(len(pts))
    reveal = max(1, FRAMES - HOLD)
    cx, cy = W / 2.0, H / 2.0
    # La escala arranca grande (el germen tiene que verse en el frame 0) y va
    # cediendo para que el cumulo entre entero: primero se ve crecer, despues
    # se ve detallarse.
    target = 0.485 * W
    scale_cap = 34.0

    scale_note = ["C3", "Eb3", "G3", "Bb3", "C4", "Eb4", "G4", "Bb4"]
    events = []

    for f in range(FRAMES):
        p = min(1.0, (f + 1) / reveal)
        n = max(12, int(len(pts) * p))
        sub = pts[:n]
        rcur = max(4.0, float(np.hypot(sub[:, 0], sub[:, 1]).max()))
        scale = min(scale_cap, target / rcur)

        # Cada particula es una celda de la grilla: a escala s ocupa s x s
        # pixeles. Dibujarla siempre como un punto deja los primeros segundos
        # casi negros, que es cuando la escala es mas grande.
        boost = float(np.clip(scale, 1.0, 8.0) ** 1.8)
        sigma = float(np.clip(0.5 * scale, 0.0, 4.0))
        img = np.zeros((H, W, 3), dtype=np.float32)
        # El color va con la posicion en lo YA revelado, no en el total: si no,
        # los primeros segundos son todos "particulas viejas" y salen en oro
        # casi negro. Asi la punta que crece esta siempre brillante.
        q = (order[:n] / max(1, n - 1))[:, None]
        col = (OLD * (1.0 - q) + NEW * q).astype(np.float32)
        col = col * (0.78 + 0.70 * q).astype(np.float32)
        splat(img, cx + sub[:, 0] * scale, cy + sub[:, 1] * scale, col)

        if sigma > 0.35:
            img = gaussian_filter(img, (sigma, sigma, 0)) * boost
        img *= 0.62
        img = 1.0 - np.exp(-2.3 * np.maximum(img, 0.0))
        img = np.clip(img + 0.80 * gaussian_filter(img, (2.1, 2.1, 0)), 0.0, 1.0)
        Image.fromarray((img * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.78})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[dla] {f + 1}/{FRAMES}  {n} particulas  escala {scale:.2f}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "n_particles": int(len(pts)), "dimension": D, "fit_r2": r2,
                   "dimension_gyration": Dg, "fit_r2_gyration": r2g,
                   "reveal_frames": reveal}, jf)
    print(f"[dla] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
