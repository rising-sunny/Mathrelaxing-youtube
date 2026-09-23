"""
Sincronizacion espontanea: el modelo de Kuramoto, con luciernagas.

    d(theta_i)/dt = omega_i + (K/N) sum_j sin(theta_j - theta_i)
                  = omega_i + K r sin(psi - theta_i),     r e^(i psi) = <e^(i theta)>

Cada luciernaga tiene su propio ritmo natural omega_i y nadie manda. Con
frecuencias de Lorentz de semiancho gamma la solucion estacionaria es exacta
(Kuramoto 1975; Ott y Antonsen 2008):

    r = 0                  si K < Kc
    r = sqrt(1 - Kc/K)     si K > Kc,       Kc = 2 gamma

Aqui eso se MIDE, no se cita: un barrido de K con 20000 osciladores desde
fases al azar, y un ajuste lineal de r^2 contra 1/K que tiene que devolver
pendiente -Kc y ordenada 1.

La fase global es una simetria exacta del modelo (sumar la misma constante a
todas las theta_i da otra solucion), asi que se elige para que, una vez
sincronizado, el enjambre destelle justo sobre el pulso de la musica.

Uso:
    python scenes/kuramoto.py -- --frames 900 --res 1920 --name shorts_k
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_k")
FPS = int(arg("--fps", 60))
N = int(arg("--n", 9000))
SUB = int(arg("--sub", 4))
SEED = int(arg("--seed", 5))

# el pulso de la musica: 16 tiempos en el bucle de 15 s
BEATS, LOOP = 16, 15.0
OMEGA0 = 2 * math.pi * BEATS / LOOP
GAMMA = float(arg("--gamma", 1.2))
KC = 2.0 * GAMMA
KMAX = float(arg("--kmax", 4.0)) * KC
T_ON = float(arg("--t-on", 1.0))
T_FULL = float(arg("--t-full", 9.5))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

W, H = int(round(RES * 9 / 16)), RES
W -= W % 2
H -= H % 2


# --------------------------------------------------------------------------
# Dinamica
# --------------------------------------------------------------------------
def lorentz_quantiles(n, gamma):
    """Frecuencias en los cuantiles exactos de una Lorentz centrada en 0.

    Con muestreo al azar el error de r es O(1/sqrt N); con cuantiles
    deterministas es O(1/N). Por eso el barrido de abajo da cuatro decimales
    y no dos."""
    return gamma * np.tan(np.pi * ((np.arange(n) + 0.5) / n - 0.5))


def rhs(th, w, K):
    z = np.exp(1j * th).mean()
    return w + K * np.imag(z * np.exp(-1j * th))


def rk4(th, w, K, dt):
    k1 = rhs(th, w, K)
    k2 = rhs(th + 0.5 * dt * k1, w, K)
    k3 = rhs(th + 0.5 * dt * k2, w, K)
    k4 = rhs(th + dt * k3, w, K)
    return th + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)


def exact_r(K):
    return math.sqrt(1.0 - KC / K) if K > KC else 0.0


def coupling(t):
    """K(t): cero al principio, sube suave y se queda arriba el final."""
    u = min(1.0, max(0.0, (t - T_ON) / (T_FULL - T_ON)))
    return KMAX * u * u * (3 - 2 * u)


def verify():
    """Barrido de K con 20000 osciladores, gamma = 1, desde fases al azar."""
    n, g, kc = 20000, 1.0, 2.0
    w = lorentz_quantiles(n, g)
    ratios = [0.5, 0.8, 1.3, 1.6, 2.0, 2.5, 3.0, 4.0]
    dt, T, avg = 0.02, 80.0, 25.0
    steps, navg = int(T / dt), int(avg / dt)
    rows = []
    for q in ratios:
        rng = np.random.default_rng(int(q * 100))
        th = rng.uniform(0, 2 * np.pi, n)
        rs = []
        for s in range(steps):
            th = rk4(th, w, q * kc, dt)
            if s >= steps - navg:
                rs.append(abs(np.exp(1j * th).mean()))
        rows.append((q, float(np.mean(rs)), math.sqrt(max(0.0, 1 - 1 / q))))
    above = [(q, r) for q, r, _ in rows if q >= 1.3]
    qa = np.array([x[0] for x in above])
    ra = np.array([x[1] for x in above])
    b, a = np.polyfit(1.0 / (qa * kc), ra ** 2, 1)
    dev = max(abs(r - e) for q, r, e in rows if q >= 1.3)
    below = max(r for q, r, _ in rows if q < 1.0)
    for q, r, e in rows:
        print(f"[k] K = {q:.1f} Kc   r {r:.4f}   exacto {e:.4f}")
    print(f"[k] ajuste r^2 = a + b/K: a = {a:.5f} (1), Kc = {-b:.5f} ({kc}); "
          f"desviacion maxima {dev:.1e}; por debajo de Kc r <= {below:.4f}")
    assert abs(a - 1.0) < 0.01, f"la ordenada del ajuste da {a:.4f}, no 1"
    assert abs(-b / kc - 1.0) < 0.01, f"el Kc ajustado da {-b:.4f}, no {kc}"
    assert dev < 0.01, f"r se aparta de sqrt(1-Kc/K) en {dev:.4f}"
    assert below < 0.05, f"por debajo de Kc r vale {below:.4f}: no es incoherente"
    return {"sweep": rows, "fit_a": float(a), "fit_kc": float(-b / kc),
            "max_dev": float(dev), "below": float(below), "n_sweep": n}


def simulate():
    rng = np.random.default_rng(SEED)
    w = OMEGA0 + lorentz_quantiles(N, GAMMA)[rng.permutation(N)]
    th = rng.uniform(0, 2 * np.pi, N)
    dt = 1.0 / (FPS * SUB)
    TH = np.empty((FRAMES, N))
    for f in range(FRAMES):
        TH[f] = th
        for s in range(SUB):
            th = rk4(th, w, coupling((f * SUB + s) * dt), dt)
    return w, TH, rng


# --------------------------------------------------------------------------
# Escenario
# --------------------------------------------------------------------------
def conifers(rng, n, base, hmin, hmax, wmin, wmax):
    """Linea de abetos: el perfil es el maximo de muchos triangulos."""
    x = np.arange(W, dtype=np.float32)
    top = np.full(W, base, np.float32)
    for _ in range(n):
        cx = rng.uniform(-0.1 * W, 1.1 * W)
        h = rng.uniform(hmin, hmax)
        hw = rng.uniform(wmin, wmax)
        # un poco de dientes de sierra en los flancos, como ramas
        prof = h - np.abs(x - cx) * (h / hw)
        prof -= 0.035 * h * (np.sin((x - cx) * 0.9) > 0.55)
        top = np.maximum(top, base + prof)
    return top


def scene(rng):
    yy = np.arange(H, dtype=np.float32)[:, None] / H
    xx = np.arange(W, dtype=np.float32)[None, :] / W
    sky = (np.array([0.008, 0.013, 0.034], np.float32) * (1 - yy[..., None])
           + np.array([0.020, 0.044, 0.058], np.float32) * yy[..., None])
    img = np.broadcast_to(sky, (H, W, 3)).copy()

    # estrellas en la mitad de arriba
    ns = 900
    sx = rng.integers(0, W, ns)
    sy = (rng.random(ns) ** 1.6 * 0.52 * H).astype(int)
    sb = rng.random(ns) ** 3.0 * 0.55
    st = np.zeros((H, W), np.float32)
    np.add.at(st, (sy, sx), sb)
    st = st + 1.4 * gaussian_filter(st, 0.8)
    img += st[..., None] * np.array([0.80, 0.86, 1.0], np.float32)

    # resplandor bajo en el horizonte
    img += (np.exp(-((yy - 0.56) / 0.10) ** 2)[..., None]
            * np.array([0.010, 0.030, 0.032], np.float32))

    def mask_from_top(top, soft=1.2):
        m = (np.arange(H, dtype=np.float32)[:, None] - (H - top)[None, :]) / soft
        return np.clip(m + 0.5, 0.0, 1.0)

    far_top = conifers(rng, 70, 0.40 * H, 0.05 * H, 0.14 * H, 0.03 * W, 0.07 * W)
    far = mask_from_top(far_top)
    img = img * (1 - far[..., None]) + far[..., None] * np.array(
        [0.012, 0.026, 0.032], np.float32)

    mid_top = conifers(rng, 34, 0.30 * H, 0.10 * H, 0.26 * H, 0.05 * W, 0.12 * W)
    mid = mask_from_top(mid_top)
    img = img * (1 - mid[..., None]) + mid[..., None] * np.array(
        [0.005, 0.011, 0.014], np.float32)

    # primer plano: pasto abajo (con troncos en los bordes se leian como
    # barras negras de marco, no como arboles)
    gx = np.arange(W, dtype=np.float32)
    grass_top = 0.085 * H + 0.012 * H * np.sin(gx * 0.043) + 0.008 * H * np.sin(gx * 0.17)
    for _ in range(260):
        cx = rng.uniform(0, W)
        hh = rng.uniform(0.02, 0.075) * H
        grass_top = np.maximum(grass_top, 0.07 * H + hh - np.abs(gx - cx) * hh / 5.0)
    near = mask_from_top(grass_top)
    img = img * (1 - near[..., None]) + near[..., None] * np.array(
        [0.002, 0.004, 0.005], np.float32)

    # donde cae la luz de rebote cuando el enjambre destella
    bounce = (np.exp(-((yy - 0.80) / 0.20) ** 2) * (1 - 0.6 * near)).astype(np.float32)
    return img.astype(np.float32), mid, near, bounce


def fireflies(rng):
    # profundidad: 0 lejos, 1 cerca. Las cercanas son bolas grandes y tienen
    # que ser escasas, o en el destello tapan el bosque entero
    z = rng.random(N) ** 1.7
    x0 = rng.uniform(-0.03, 1.03, N) * W
    lo = 0.47 - 0.14 * z
    hi = 0.64 + 0.29 * z
    y0 = (lo + (hi - lo) * rng.random(N)) * H
    wander = {
        "ax": (5 + 22 * z), "ay": (4 + 15 * z),
        "fx": rng.uniform(0.05, 0.17, N), "fy": rng.uniform(0.04, 0.14, N),
        "px": rng.uniform(0, 2 * np.pi, N), "py": rng.uniform(0, 2 * np.pi, N),
    }
    return z, x0, y0, wander


def splat(x, y, wgt):
    """Deposito bilineal con bincount (np.add.at es diez veces mas lento)."""
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    out = np.zeros(H * W, np.float64)
    for dx, dy, ww in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                       (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xi, yi = x0 + dx, y0 + dy
        ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
        out += np.bincount((yi[ok] * W + xi[ok]), weights=(wgt * ww)[ok],
                           minlength=H * W)
    return out.reshape(H, W).astype(np.float32)


CORE = np.array([0.86, 1.00, 0.34], np.float32)     # chartreuse, no beige
HALO = np.array([0.42, 0.95, 0.14], np.float32)
# (z desde, z hasta, sigma nucleo, sigma halo, ganancia). Las cercanas son
# bolas grandes y desenfocadas; las lejanas, puntas de alfiler.
LAYERS = ((0.00, 0.33, 0.8, 2.6, 0.95), (0.33, 0.88, 1.4, 4.2, 1.0),
          (0.88, 1.01, 3.4, 11.0, 0.85))
KAPPA = 16.0                                       # ancho del destello
PULSE_MEAN = math.exp(-KAPPA) * float(np.i0(KAPPA))


def prepare():
    w, TH, rng = simulate()
    t = np.arange(FRAMES) / FPS
    Z = np.exp(1j * TH).mean(axis=1)
    R, PSI = np.abs(Z), np.angle(Z)
    Ks = np.array([coupling(x) for x in t])

    # La fase global es libre: se fija para que el enjambre sincronizado
    # destelle sobre el pulso. Con frecuencias simetricas alrededor de OMEGA0
    # el grupo enganchado gira exactamente a OMEGA0, asi que psi - OMEGA0 t es
    # constante en el tramo final.
    hold = t > T_FULL + 1.5
    delta = float(np.angle(np.mean(np.exp(1j * (PSI[hold] - OMEGA0 * t[hold])))))
    TH -= delta
    PSI = np.angle(np.exp(1j * (PSI - delta)))
    lag = np.angle(np.exp(1j * (PSI[hold] - OMEGA0 * t[hold])))
    beat_ms = float(np.sqrt(np.mean(lag ** 2)) / OMEGA0 * 1000)
    print(f"[k] enjambre sobre el pulso con desfase rms de {beat_ms:.1f} ms")

    bg, mid_m, near_m, bounce = scene(rng)
    z, x0, y0, wd = fireflies(rng)
    return {
        "w": w, "TH": TH, "t": t, "R": R, "PSI": PSI, "Ks": Ks, "beat_ms": beat_ms,
        "bg": bg, "mid_m": mid_m, "near_m": near_m, "bounce": bounce,
        "z": z, "x0": x0, "y0": y0, "wd": wd,
        "fast": np.abs(w - OMEGA0) > 40.0,      # parpadeo mas rapido que el video
        "size_w": (0.18 + 1.5 * z * z) * (0.30 + 0.90 * z),
        "sub": rng.choice(N, 600, replace=False),
        "jit": 0.90 + 0.10 * rng.random(600),
    }


def render_frame(c, f):
    th, t = c["TH"][f], c["t"]
    z, wd, fast = c["z"], c["wd"], c["fast"]
    p = np.exp(KAPPA * (np.cos(th) - 1.0))
    p[fast] = PULSE_MEAN
    b = (0.02 + p) * c["size_w"]
    xs = c["x0"] + wd["ax"] * np.sin(2 * np.pi * wd["fx"] * t[f] + wd["px"])
    ys = c["y0"] + wd["ay"] * np.sin(2 * np.pi * wd["fy"] * t[f] + wd["py"])

    img = c["bg"].copy()
    for zl, zh, sc, sh, gain in LAYERS:
        m = (z >= zl) & (z < zh)
        d = splat(xs[m], ys[m], b[m])
        core = gaussian_filter(d, sc)
        halo = gaussian_filter(d, sh)
        # El pico de un punto desenfocado cae como 1/sigma^2: sin compensarlo
        # las cercanas, que son las mas borrosas, salen las mas apagadas. Y el
        # nucleo manda sobre el halo, o el enjambre se lee como neblina.
        light = (gain * 0.80 * 2 * np.pi * sc * sc * core[..., None] * CORE
                 + gain * 0.045 * 2 * np.pi * sh * sh * halo[..., None] * HALO)
        if zh <= 0.33:
            light *= ((1 - c["mid_m"]) * (1 - c["near_m"]))[..., None]
        elif zh <= 0.88:
            light *= (1 - c["near_m"])[..., None]
        img += light

    amb = float(np.mean(p[~fast]))
    img += (0.045 * amb) * c["bounce"][..., None] * HALO
    out = 1.0 - np.exp(-1.25 * np.maximum(img, 0.0))

    # el circulo de fases: cada punto es una luciernaga, la flecha es r
    cx, cy, Rc, SS = W / 2, 0.745 * H, 0.125 * W, 2
    box = int(3.0 * Rc) // 2 * 2
    lay = Image.new("RGBA", (box * SS, box * SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lay)
    cc, rr = box * SS / 2, Rc * SS
    dr.ellipse([cc - 1.32 * rr, cc - 1.32 * rr, cc + 1.32 * rr, cc + 1.32 * rr],
               fill=(3, 7, 9, 150))
    dr.ellipse([cc - rr, cc - rr, cc + rr, cc + rr],
               outline=(70, 110, 90, 150), width=SS)
    dr.line([(cc, cc - rr - 9 * SS), (cc, cc - rr + 5 * SS)],
            fill=(255, 225, 120, 230), width=2 * SS)
    sub, jit = c["sub"], c["jit"]
    ps = p[sub]
    for k in range(len(sub)):
        a = th[sub[k]]
        px_ = cc + rr * jit[k] * math.sin(a)
        py_ = cc - rr * jit[k] * math.cos(a)
        q = ps[k]
        col = (int(70 + 185 * q), int(130 + 120 * q), int(70 + 30 * q), 225)
        rad = SS * (1.3 + 1.5 * q)
        dr.ellipse([px_ - rad, py_ - rad, px_ + rad, py_ + rad], fill=col)
    ang, L = c["PSI"][f], c["R"][f] * rr
    ex, ey = cc + L * math.sin(ang), cc - L * math.cos(ang)
    dr.line([(cc, cc), (ex, ey)], fill=(255, 196, 92, 255), width=3 * SS)
    dr.ellipse([cc - 3 * SS, cc - 3 * SS, cc + 3 * SS, cc + 3 * SS],
               fill=(255, 196, 92, 255))
    if L > 6 * SS:
        ux, uy = (ex - cc) / L, (ey - cc) / L
        hl = 11 * SS
        dr.polygon([(ex, ey),
                    (ex - hl * ux + 0.55 * hl * uy, ey - hl * uy - 0.55 * hl * ux),
                    (ex - hl * ux - 0.55 * hl * uy, ey - hl * uy + 0.55 * hl * ux)],
                   fill=(255, 196, 92, 255))
    lay = lay.resize((box, box), Image.LANCZOS)
    frame = Image.fromarray((out * 255).astype(np.uint8), "RGB")
    frame.paste(lay, (int(cx - box / 2), int(cy - box / 2)), lay)
    return frame, p


def main():
    ver = verify()
    c = prepare()
    w, R, Ks, t = c["w"], c["R"], c["Ks"], c["t"]
    events, shown = [], []
    for f in range(FRAMES):
        frame, _ = render_frame(c, f)
        frame.save(os.path.join(FRAMES_DIR, f"{f:04d}.png"))
        K = Ks[f]
        locked = float(np.mean(np.abs(w - OMEGA0) <= K * R[f])) if K > 0 else 0.0
        shown.append({"t": float(t[f]), "k_over_kc": float(K / KC), "r": float(R[f]),
                      "r_exact": exact_r(K), "locked": locked})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[k] {f+1}/{FRAMES}  K={K/KC:.2f} Kc  r={R[f]:.3f} "
                  f"(exacto {exact_r(K):.3f})  enganchadas {locked*100:.0f}%")

    for k in range(BEATS):
        events.append({"frame": int(round(k * LOOP / BEATS * FPS)),
                       "note": "D5", "intensity": 0.6})
    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "n": N, "gamma": GAMMA, "kc": KC, "kmax_over_kc": KMAX / KC,
                   "omega0": OMEGA0, "beat_ms": c["beat_ms"], "shown": shown,
                   "verify": ver}, jf)
    print(f"[k] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
