"""
Cuatro materiales, una ecuacion: MPM (Material Point Method) con Taichi.

Todo lo que se ve -- gelatina, nieve, arena y agua -- obedece la MISMA ley,
la conservacion del momento de un medio continuo,

    rho Dv/Dt = div(sigma) + rho g,

y lo unico que cambia es como responde cada material a la deformacion F
(la "ley constitutiva" que da la tension sigma):

    gelatina   elastica (corrotacional fija): vuelve a su forma
    nieve      la misma, pero se rompe: los valores singulares de F se
               recortan a [1 - 2.5e-2, 1 + 4.5e-3] (Stomakhin et al. 2013)
    arena      Drucker-Prager: friccion de Coulomb en deformacion
               logaritmica, sin cohesion (Klar et al. 2016)
    agua       solo presion: sigma = K (J - 1) J I

MLS-MPM (Hu et al. 2018): particulas -> rejilla -> particulas en cada paso.

Se comprueba antes de dibujar:
  1) la masa que las particulas dejan en la rejilla es exactamente la suya;
  2) un bloque en caida libre acelera exactamente g (APIC conserva momento);
  3) una cuna de arena de 18 grados se queda quieta y las de 45 y 60 se
     derrumban: la arena aguanta pendientes suaves y no empinadas.

Uso:
    python scenes/mpm_materials.py -- --frames 900 --res 1920 --name shorts_mpm
"""
import json
import math
import os
import sys

import numpy as np
import taichi as ti
from PIL import Image
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_mpm")
FPS = int(arg("--fps", 60))
SEED = int(arg("--seed", 4))
ONLY = {int(x) for x in arg("--only", "").split(",") if x}

H = RES
W = RES * 9 // 16
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "output", NAME)
FRAMES_DIR = os.path.join(OUT, "frames")
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

ti.init(arch=ti.cpu, default_fp=ti.f32, random_seed=SEED)

NX = 256
NY = int(round(NX * 16 / 9))
DX = 1.0 / NX
INV_DX = float(NX)
YMAX = NY * DX
DT = 4e-5
P_VOL = (DX * 0.5) ** 2
P_RHO = 1.0
P_MASS = P_VOL * P_RHO
E, NU = 5e3, 0.2
MU0, LA0 = E / (2 * (1 + NU)), E * NU / ((1 + NU) * (1 - 2 * NU))
GRAV = 20.0
PHI_DEG = 40.0                                  # angulo de friccion de la arena
SIN_PHI = math.sin(math.radians(PHI_DEG))
ALPHA = math.sqrt(2 / 3) * 2 * SIN_PHI / (3 - SIN_PHI)
SIM_PER_S = 0.23                                # segundos simulados por segundo de video
MAXP = 120000

WATER, JELLY, SNOW, SAND = 0, 1, 2, 3

# escenario (unidades de simulacion: ancho 1, alto YMAX)
FLOOR = 0.25
WALL_L, WALL_R = 0.02, 0.98
PEGS = [(0.28, 0.78, 0.05), (0.75, 0.93, 0.05)]
HOP = (0.42, 0.58, 1.10, 1.36)                  # tolva: x0, x1, y0, y1
HOP_OPEN = 0.035                                # media apertura del fondo
GATE_X = 0.63
TANK_TOP = 0.60

# guion (segundos de video)
T_SNOW = 2.2
T_SAND = 4.0
T_GATE = 7.4
TILT = [(0.0, 0.0), (10.6, 0.0), (11.4, 14.0), (12.8, 14.0), (13.6, -14.0),
        (14.2, -14.0), (15.0, 0.0)]                # giro de la caja (grados, antihorario)
PIVOT = (0.5, FLOOR + 0.1)


def tilt_deg(t):
    ts, vs = zip(*TILT)
    k = int(np.searchsorted(ts, t, side="right")) - 1
    if k >= len(ts) - 1:
        return vs[-1]
    u = (t - ts[k]) / (ts[k + 1] - ts[k])
    u = u * u * (3 - 2 * u)
    return vs[k] + (vs[k + 1] - vs[k]) * u

x = ti.Vector.field(2, float, MAXP)
v = ti.Vector.field(2, float, MAXP)
C = ti.Matrix.field(2, 2, float, MAXP)
F = ti.Matrix.field(2, 2, float, MAXP)
Jp = ti.field(float, MAXP)
mat = ti.field(int, MAXP)
act = ti.field(int, MAXP)
grid_v = ti.Vector.field(2, float, (NX, NY))
grid_m = ti.field(float, (NX, NY))
n_part = ti.field(int, ())
g_on = ti.field(float, ())                      # gravedad (0 para pruebas)
hop_open = ti.field(int, ())
gate_y = ti.field(float, ())                    # borde inferior de la compuerta
walls_on = ti.field(int, ())
gvec = ti.Vector.field(2, float, ())         # gravedad en el marco de la caja


@ti.kernel
def p2g():
    for i, j in grid_m:
        grid_v[i, j] = [0, 0]
        grid_m[i, j] = 0
    for p in range(n_part[None]):
        if act[p] == 0:
            continue
        base = (x[p] * INV_DX - 0.5).cast(int)
        fx = x[p] * INV_DX - base.cast(float)
        w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1) ** 2, 0.5 * (fx - 0.5) ** 2]
        F[p] = (ti.Matrix.identity(float, 2) + DT * C[p]) @ F[p]
        m = mat[p]
        h = 1.0
        if m == SNOW:
            h = ti.exp(10 * (1.0 - Jp[p]))
        if m == JELLY:
            h = 0.3
        mu, la = MU0 * h, LA0 * h
        if m == WATER:
            mu = 0.0
        U, sig, V = ti.svd(F[p])
        stress = ti.Matrix.zero(float, 2, 2)
        if m == SAND:
            # Drucker-Prager en deformacion logaritmica, sin cohesion
            e0 = ti.log(ti.max(sig[0, 0], 1e-6))
            e1 = ti.log(ti.max(sig[1, 1], 1e-6))
            tr = e0 + e1
            if tr >= 0:
                e0, e1 = 0.0, 0.0
            else:
                h0, h1 = e0 - tr / 2, e1 - tr / 2
                nh = ti.sqrt(h0 * h0 + h1 * h1)
                dg = nh + (2 * la + 2 * mu) / (2 * mu) * tr * ALPHA
                if dg > 0 and nh > 1e-10:
                    e0 -= dg / nh * h0
                    e1 -= dg / nh * h1
            sig[0, 0] = ti.exp(e0)
            sig[1, 1] = ti.exp(e1)
            F[p] = U @ sig @ V.transpose()
            # Kirchhoff de Hencky: U (2 mu ln S + la tr(ln S) I) U^T
            tr2 = e0 + e1
            dg_ = ti.Matrix([[2 * mu * e0 + la * tr2, 0], [0, 2 * mu * e1 + la * tr2]])
            stress = U @ dg_ @ U.transpose()
        else:
            J = 1.0
            for d in ti.static(range(2)):
                ns = sig[d, d]
                if m == SNOW:
                    ns = ti.min(ti.max(sig[d, d], 1 - 2.5e-2), 1 + 3.0e-3)
                Jp[p] *= sig[d, d] / ns
                sig[d, d] = ns
                J *= ns
            if m == WATER:
                F[p] = ti.Matrix.identity(float, 2) * ti.sqrt(J)
            elif m == SNOW:
                F[p] = U @ sig @ V.transpose()
            R = U @ V.transpose()
            stress = 2 * mu * (F[p] - R) @ F[p].transpose() + \
                ti.Matrix.identity(float, 2) * la * J * (J - 1)
        stress = (-DT * P_VOL * 4 * INV_DX * INV_DX) * stress
        affine = stress + P_MASS * C[p]
        for i, j in ti.static(ti.ndrange(3, 3)):
            off = ti.Vector([i, j])
            dpos = (off.cast(float) - fx) * DX
            wt = w[i][0] * w[j][1]
            grid_v[base + off] += wt * (P_MASS * v[p] + affine @ dpos)
            grid_m[base + off] += wt * P_MASS


@ti.kernel
def grid_update():
    for i, j in grid_m:
        if grid_m[i, j] > 0:
            grid_v[i, j] = grid_v[i, j] / grid_m[i, j]
            grid_v[i, j] += DT * GRAV * g_on[None] * gvec[None]
            px, py = i * DX, j * DX
            # caja
            if walls_on[None] == 1:
                # paredes con roce: sin esto el agua trepa en chorros finos
                if px < WALL_L:
                    grid_v[i, j][0] = ti.max(grid_v[i, j][0], 0.0)
                    grid_v[i, j][1] *= 0.9
                if px > WALL_R:
                    grid_v[i, j][0] = ti.min(grid_v[i, j][0], 0.0)
                    grid_v[i, j][1] *= 0.9
                if py < FLOOR:
                    grid_v[i, j][1] = ti.max(grid_v[i, j][1], 0.0)
                    grid_v[i, j][0] *= 0.6                      # roce con el suelo
                # postes: deslizamiento, sin entrar
                for k in ti.static(range(len(PEGS))):
                    cx, cy, r = PEGS[k]
                    d = ti.Vector([px - cx, py - cy])
                    dn = d.norm()
                    if dn < r + DX:
                        nrm = d / ti.max(dn, 1e-6)
                        vn = grid_v[i, j].dot(nrm)
                        if vn < 0:
                            grid_v[i, j] -= vn * nrm
                # tolva: paredes inclinadas y fondo que se abre
                x0, x1, y0, y1 = HOP
                if py > y0 - DX and py < y1:
                    frac = (py - y0) / (y1 - y0)
                    left = 0.5 - HOP_OPEN - (0.5 - HOP_OPEN - x0) * frac
                    right = 0.5 + HOP_OPEN + (x1 - 0.5 - HOP_OPEN) * frac
                    if ti.abs(px - left) < 1.5 * DX and grid_v[i, j][0] < 0:
                        grid_v[i, j][0] = 0
                    if ti.abs(px - right) < 1.5 * DX and grid_v[i, j][0] > 0:
                        grid_v[i, j][0] = 0
                    if ti.abs(px - left) < 1.5 * DX or ti.abs(px - right) < 1.5 * DX:
                        grid_v[i, j][1] = ti.max(grid_v[i, j][1], -0.02)
                if hop_open[None] == 0 and ti.abs(py - y0) < 1.5 * DX and \
                        ti.abs(px - 0.5) < HOP_OPEN + DX:
                    grid_v[i, j][1] = ti.max(grid_v[i, j][1], 0.0)
                # compuerta del deposito: se levanta desde abajo
                if ti.abs(px - GATE_X) < 1.5 * DX and py > gate_y[None] and \
                        py < TANK_TOP + 0.22 and grid_v[i, j][0] < 0:
                    grid_v[i, j][0] = 0
                    grid_v[i, j][1] *= 0.9


@ti.kernel
def g2p():
    for p in range(n_part[None]):
        if act[p] == 0:
            continue
        base = (x[p] * INV_DX - 0.5).cast(int)
        fx = x[p] * INV_DX - base.cast(float)
        w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
        nv = ti.Vector.zero(float, 2)
        nC = ti.Matrix.zero(float, 2, 2)
        for i, j in ti.static(ti.ndrange(3, 3)):
            off = ti.Vector([i, j])
            dpos = off.cast(float) - fx
            gv = grid_v[base + off]
            wt = w[i][0] * w[j][1]
            nv += wt * gv
            nC += 4 * INV_DX * wt * gv.outer_product(dpos)
        v[p], C[p] = nv, nC
        x[p] += DT * v[p]
        x[p][0] = ti.min(ti.max(x[p][0], 3 * DX), 1 - 3 * DX)
        x[p][1] = ti.min(ti.max(x[p][1], 3 * DX), YMAX - 3 * DX)


def step():
    p2g()
    grid_update()
    g2p()


@ti.kernel
def grid_mass() -> float:
    s = 0.0
    for i, j in grid_m:
        s += grid_m[i, j]
    return s


# ------------------------------------------------------------ escenario
def place(pts, material, vel=(0.0, 0.0), active=1):
    k = n_part[None]
    m = len(pts)
    assert k + m <= MAXP
    xs = x.to_numpy()
    xs[k:k + m] = pts
    x.from_numpy(xs)
    for f_, val in ((v, np.tile(vel, (m, 1))),):
        a = f_.to_numpy()
        a[k:k + m] = val
        f_.from_numpy(a)
    a = F.to_numpy()
    a[k:k + m] = np.eye(2)
    F.from_numpy(a)
    a = C.to_numpy()
    a[k:k + m] = 0
    C.from_numpy(a)
    a = Jp.to_numpy()
    a[k:k + m] = 1
    Jp.from_numpy(a)
    a = mat.to_numpy()
    a[k:k + m] = material
    mat.from_numpy(a)
    a = act.to_numpy()
    a[k:k + m] = active
    act.from_numpy(a)
    n_part[None] = k + m
    return np.arange(k, k + m)


def lattice(x0, x1, y0, y1, rng, keep=None):
    """particulas a medio paso de rejilla con un poco de jitter"""
    s = DX / 2
    gx, gy = np.meshgrid(np.arange(x0 + s / 2, x1, s), np.arange(y0 + s / 2, y1, s))
    pts = np.stack([gx.ravel(), gy.ravel()], 1)
    pts += rng.uniform(-0.25, 0.25, pts.shape) * s
    if keep is not None:
        pts = pts[keep(pts)]
    return pts


def reset():
    n_part[None] = 0
    act.from_numpy(np.zeros(MAXP, np.int32))
    g_on[None] = 1.0
    gvec[None] = [0.0, -1.0]
    walls_on[None] = 1
    hop_open[None] = 0
    gate_y[None] = FLOOR - 0.1


def verify():
    rng = np.random.default_rng(0)
    # 1) y 2): bloque de gelatina en el aire, sin paredes, con gravedad
    reset()
    walls_on[None] = 0
    ids = place(lattice(0.4, 0.6, 1.0, 1.2, rng), JELLY, vel=(0.3, 0.0))
    step()
    m_grid = grid_mass()
    m_part = len(ids) * P_MASS
    mass_err = abs(m_grid / m_part - 1)
    v0 = v.to_numpy()[ids].mean(0)
    nst = 400
    for _ in range(nst - 1):
        step()
    v1 = v.to_numpy()[ids].mean(0)
    acc = (v1 - v0) / ((nst - 1) * DT)
    g_err = abs(-acc[1] / GRAV - 1)
    vx_err = abs(v1[0] - v0[0])
    # 3) cunas de arena: una suave tiene que quedarse quieta y las empinadas
    #    tienen que derrumbarse (friccion de Coulomb, no pegamento)
    def wedge(theta, T=0.6):
        reset()
        tn = math.tan(math.radians(theta))
        hmax = min(0.2, 0.38 * tn)
        half = hmax / tn
        pts = lattice(0.5 - half, 0.5 + half, FLOOR, FLOOR + hmax, rng,
                      lambda p: (p[:, 1] - FLOOR) < hmax - np.abs(p[:, 0] - 0.5) * tn)
        ids = place(pts, SAND)
        for _ in range(int(T / DT)):
            step()
        return slope_angle(x.to_numpy()[ids])
    th_lo, th_hi = 18.0, (45.0, 60.0)
    a_lo = wedge(th_lo)
    a_hi = [wedge(t) for t in th_hi]
    ang = float(np.mean(a_hi))
    print(f"[mpm] masa en la rejilla: error {mass_err:.1e} | caida libre: "
          f"a = {-acc[1]:.4f} contra g = {GRAV} ({g_err:.1e}), vx sin cambio "
          f"({vx_err:.1e}) | arena: cuna de {th_lo:.0f} grados queda en {a_lo:.1f}; "
          f"las de {th_hi[0]:.0f} y {th_hi[1]:.0f} caen a {a_hi[0]:.1f} y {a_hi[1]:.1f}")
    assert mass_err < 1e-5, "la rejilla no recibe toda la masa"
    assert g_err < 1e-4 and vx_err < 1e-5, "la caida libre no da g"
    assert abs(a_lo - th_lo) < 2.5, "una pendiente suave de arena no deberia moverse"
    assert ang < th_lo + 25 and all(a < t - 8 for a, t in zip(a_hi, th_hi)), \
        "las pendientes empinadas tienen que derrumbarse"
    return {"mass_err": float(mass_err), "g_err": float(g_err), "repose_deg": float(ang),
            "wedges": {"start": [float(th_lo), *map(float, th_hi)],
                       "end": [float(a_lo), *map(float, a_hi)]}}


def slope_angle(ps):
    bins = np.linspace(0.02, 0.98, 97)
    idx = np.digitize(ps[:, 0], bins)
    hgt = np.array([ps[idx == k, 1].max() - FLOOR if np.any(idx == k) else 0.0
                    for k in range(1, len(bins))])
    xc = 0.5 * (bins[1:] + bins[:-1])
    top = hgt.max()
    out = []
    for side in (xc < 0.5, xc > 0.5):
        sel = side & (hgt > 0.2 * top) & (hgt < 0.8 * top)
        out.append(math.degrees(math.atan(abs(np.polyfit(xc[sel], hgt[sel], 1)[0]))))
    return float(np.mean(out))


def build_scene(rng):
    reset()
    groups = {}
    # agua en el deposito, detras de la compuerta
    groups["water"] = place(lattice(GATE_X + DX, WALL_R - DX, FLOOR, TANK_TOP, rng), WATER)
    # arena en la tolva
    x0, x1, y0, y1 = HOP

    def in_hop(p):
        frac = (p[:, 1] - y0) / (y1 - y0)
        left = 0.5 - HOP_OPEN - (0.5 - HOP_OPEN - x0) * frac
        right = 0.5 + HOP_OPEN + (x1 - 0.5 - HOP_OPEN) * frac
        return (p[:, 0] > left + 2 * DX) & (p[:, 0] < right - 2 * DX)
    groups["sand"] = place(lattice(x0, x1, y0 + DX, y1 - 0.02, rng, in_hop), SAND)
    # gelatina: bloque que cae sobre el poste izquierdo
    groups["jelly"] = place(lattice(0.08, 0.26, 1.05, 1.23, rng), JELLY, vel=(0.0, 0.0))
    # nieve: bola, entra en escena mas tarde (inactiva hasta entonces)
    groups["snow"] = place(lattice(0.66, 0.84, 1.16, 1.34, rng,
                                   lambda p: np.hypot(p[:, 0] - 0.75, p[:, 1] - 1.25) < 0.088),
                           SNOW, vel=(0.0, -0.5), active=0)
    return groups


# ------------------------------------------------------------------ dibujo
def to_px(p):
    return p[:, 0] * W, H - p[:, 1] / YMAX * H


def splat(acc, xs, ys, w):
    xi = np.floor(xs).astype(int)
    yi = np.floor(ys).astype(int)
    fx, fy = xs - xi, ys - yi
    ok = (xi >= 0) & (xi < W - 1) & (yi >= 0) & (yi < H - 1)
    xi, yi, fx, fy, w = xi[ok], yi[ok], fx[ok], fy[ok], w[ok]
    for dx, dy, ww in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                       (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        acc += np.bincount((yi + dy) * W + xi + dx, w * ww,
                           minlength=H * W).reshape(H, W)


def sim_px(xs, ys):
    return xs * W, H - ys / YMAX * H


def static_layers():
    """fondo, suelo, postes y tolva: no cambian"""
    yy, xx = np.mgrid[0:H, 0:W]
    u = yy / H
    bg = np.stack([0.030 + 0.03 * u, 0.035 + 0.035 * u, 0.07 + 0.05 * u], -1)
    r = np.hypot((xx - W / 2) / W, (yy - H * 0.55) / H)
    bg *= (1 - 0.55 * r ** 2)[..., None]
    # rejilla de laboratorio muy tenue
    gx = np.abs(((xx / W) / 0.05 + 0.5) % 1 - 0.5) < 0.012
    gy = np.abs((((H - yy) / H * YMAX) / 0.05 + 0.5) % 1 - 0.5) < 0.012
    bg += ((gx | gy) * 0.018)[..., None]
    fy = H - FLOOR / YMAX * H
    floor = yy > fy
    bg[floor] = np.array([0.055, 0.06, 0.08]) * (1 - 0.4 * ((yy[floor] - fy) / (H - fy)))[:, None]
    bg[(np.abs(yy - fy) < 1.5)] = [0.35, 0.40, 0.50]
    fg = np.zeros((H, W, 4))                      # rgb + alfa, va encima de todo
    for cx, cy, rr in PEGS:
        px, py = sim_px(cx, cy)
        rp = rr * W
        d = np.hypot(xx - px, yy - py)
        m = np.clip(rp - d + 0.5, 0, 1)
        lx, ly = (xx - px) / rp, (yy - py) / rp
        shade = np.clip(0.45 - 0.35 * lx - 0.45 * ly, 0.05, 1)
        spec = np.exp(-((lx + 0.35) ** 2 + (ly + 0.45) ** 2) / 0.02)
        col = np.stack([0.55 * shade + spec, 0.58 * shade + spec, 0.66 * shade + spec], -1)
        fg[..., :3] = fg[..., :3] * (1 - m[..., None]) + col * m[..., None]
        fg[..., 3] = np.maximum(fg[..., 3], m)
    # tolva de vidrio
    x0, x1, y0, y1 = HOP
    gl = np.zeros((H, W))
    for fr in np.linspace(0, 1, 400):
        yv = y0 + (y1 - y0) * fr
        for xv in (0.5 - HOP_OPEN - (0.5 - HOP_OPEN - x0) * fr,
                   0.5 + HOP_OPEN + (x1 - 0.5 - HOP_OPEN) * fr):
            px, py = sim_px(xv, yv)
            gl[int(py), int(px)] = 1
    gl = np.clip(gaussian_filter(gl, 1.0) * 5, 0, 1)
    glass = np.array([0.55, 0.80, 1.0])
    fg[..., :3] += gl[..., None] * glass
    fg[..., 3] = np.maximum(fg[..., 3], gl * 0.8)
    world = np.stack([0.012 + 0.015 * u, 0.014 + 0.016 * u, 0.03 + 0.02 * u], -1)
    return {"bg": bg, "fg": fg, "xx": xx, "yy": yy, "world": world}


def splat_rgbw(xs, ys, cols, w):
    acc = np.zeros((4, H * W))
    xi = np.floor(xs).astype(int)
    yi = np.floor(ys).astype(int)
    fx, fy = xs - xi, ys - yi
    ok = (xi >= 0) & (xi < W - 1) & (yi >= 0) & (yi < H - 1)
    xi, yi, fx, fy, w, cols = xi[ok], yi[ok], fx[ok], fy[ok], w[ok], cols[ok]
    for dx, dy, ww in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                       (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        idx = (yi + dy) * W + xi + dx
        wt = w * ww
        acc[3] += np.bincount(idx, wt, minlength=H * W)
        for c in range(3):
            acc[c] += np.bincount(idx, wt * cols[:, c], minlength=H * W)
    return acc.reshape(4, H, W)


def render(ps, vs, ms, ac, rest, tone, t, st):
    sel = ac == 1
    ps, vs, ms, rest, tone = ps[sel], vs[sel], ms[sel], rest[sel], tone[sel]
    xs, ys = sim_px(ps[:, 0], ps[:, 1])
    cols = np.zeros((len(ps), 3))
    sp = np.linalg.norm(vs, axis=1)
    # agua: azul que se aclara con la velocidad, espuma blanca si va rapida
    w_ = ms == WATER
    foam = np.clip((sp[w_] - 1.2) / 1.5, 0, 1)[:, None]
    cols[w_] = np.array([0.08, 0.42, 0.98]) * (1 - foam) + np.array([0.90, 0.97, 1.0]) * foam
    # gelatina: cuadricula pintada en su forma de reposo -> se ve la deformacion
    j_ = ms == JELLY
    cx = np.floor((rest[j_, 0] - 0.08) / 0.03) + np.floor((rest[j_, 1] - 1.05) / 0.03)
    chk = (cx % 2)[:, None]
    cols[j_] = np.array([0.20, 0.95, 0.72]) * chk + np.array([0.95, 0.30, 0.62]) * (1 - chk)
    s_ = ms == SNOW
    cols[s_] = np.array([1.12, 1.15, 1.2]) * tone[s_, None] ** 0.25
    a_ = ms == SAND
    cols[a_] = np.array([0.95, 0.70, 0.33]) * tone[a_, None]
    # el agua se suaviza mas que los solidos: es una superficie continua
    rgb = np.zeros((H, W, 3))
    wsum = np.zeros((H, W))
    for sig_, sel_ in ((2.2, w_), (1.1, ~w_)):
        if not sel_.any():
            continue
        acc = splat_rgbw(xs[sel_], ys[sel_], cols[sel_], np.ones(sel_.sum()))
        ws = gaussian_filter(acc[3], sig_)
        wsum += ws
        for c in range(3):
            rgb[..., c] += gaussian_filter(acc[c], sig_)
    rgb /= np.maximum(wsum, 1e-6)[..., None]
    alpha = np.clip(1 - np.exp(-wsum * 1.8), 0, 1)
    # relieve: normal a partir de la cobertura suavizada -> luz desde arriba a la izquierda
    hgt = gaussian_filter(alpha, 3.0)
    gy, gx = np.gradient(hgt)
    nx, ny, nz = -gx * 9, -gy * 9, np.ones_like(gx)
    nn = np.sqrt(nx * nx + ny * ny + nz * nz)
    lx, ly, lz = -0.45, -0.6, 0.66
    lam = np.clip((nx * lx + ny * ly + nz * lz) / nn, 0, 1)
    # especular solo en agua y gelatina
    wet = np.zeros(len(ps))
    wet[w_] = 1.0
    wet[j_] = 0.7
    accw = splat_rgbw(xs, ys, np.zeros((len(ps), 3)), wet)[3]
    wetm = np.clip(gaussian_filter(accw, 2.0) / np.maximum(wsum, 1e-6), 0, 1)
    hx, hy, hz_ = lx, ly, lz + 1
    hn = math.sqrt(hx * hx + hy * hy + hz_ * hz_)
    spec = np.clip((nx * hx + ny * hy + nz * hz_) / (nn * hn), 0, 1) ** 40 * wetm
    shade = 0.55 + 0.6 * lam
    mat_img = rgb * shade[..., None] + spec[..., None] * 0.8
    img = st["bg"] * (1 - alpha[..., None]) + mat_img * alpha[..., None]
    # compuerta: panel metalico que sube
    gx0 = GATE_X * W
    gyb = H - max(gate_y[None], FLOOR) / YMAX * H
    gyt = H - (TANK_TOP + 0.22) / YMAX * H
    pan = (np.abs(st["xx"] - gx0) < 5) & (st["yy"] < gyb) & (st["yy"] > gyt)
    img[pan] = img[pan] * 0.2 + np.array([0.50, 0.55, 0.62]) * 0.8
    fg = st["fg"]
    img = img * (1 - fg[..., 3:]) + fg[..., :3]
    # brillo suave de lo mas claro
    lum = img.max(-1)
    bloom = gaussian_filter(np.clip(lum - 0.75, 0, None), 8)
    img += bloom[..., None] * np.array([0.6, 0.75, 1.0]) * 0.8
    th = tilt_deg(t)
    if abs(th) > 1e-3:
        img = rotate_box(img, th, st)
    return np.clip(img, 0, 1) ** 0.92


def rotate_box(img, deg, st):
    """la caja gira alrededor de un punto del suelo; afuera queda el fondo"""
    from scipy.ndimage import affine_transform
    px, py = sim_px(*PIVOT)
    a = math.radians(deg)
    # en pantalla (y hacia abajo) un giro antihorario es R(-a) en (fila, col)
    ca, sa = math.cos(a), math.sin(a)
    M = np.array([[ca, -sa], [sa, ca]])            # destino -> origen, en (fila, col)
    c = np.array([py, px])
    off = c - M @ c
    out = np.empty_like(img)
    for k in range(3):
        out[..., k] = affine_transform(img[..., k], M, offset=off, order=1, cval=-1.0)
    mask = out[..., 0] >= 0
    world = st["world"]
    return np.where(mask[..., None], out, world)


def save(f, img):
    if ONLY and f not in ONLY:
        return
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(FRAMES_DIR, f"{f + 1:04d}.png"))


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)
    ver = verify() if "--no-verify" not in argv else {}
    rng = np.random.default_rng(SEED)
    groups = build_scene(rng)
    n = n_part[None]
    rest = x.to_numpy()[:n].copy()               # coordenadas de material (textura)
    tone = rng.uniform(0.75, 1.15, n)
    sub = int(round(SIM_PER_S / FPS / DT))
    print(f"[mpm] {n} particulas | {sub} subpasos por cuadro | rejilla {NX}x{NY}")
    static = static_layers()
    shown = []
    for f in range(FRAMES):
        t = f / FPS
        if t >= T_SNOW:
            a = act.to_numpy()
            if a[groups["snow"][0]] == 0:
                a[groups["snow"]] = 1
                act.from_numpy(a)
        hop_open[None] = 1 if t >= T_SAND else 0
        gate_y[None] = FLOOR - 0.1 + max(0.0, min(1.0, (t - T_GATE) / 0.25)) * 0.6
        # la caja gira un angulo th: en su marco la gravedad gira -th
        th = math.radians(tilt_deg(t))
        gvec[None] = [-math.sin(th), -math.cos(th)]
        for _ in range(sub):
            step()
        shown.append({"t": t})
        if ONLY and f not in ONLY:
            continue
        img = render(x.to_numpy()[:n], v.to_numpy()[:n], mat.to_numpy()[:n],
                     act.to_numpy()[:n], rest, tone, t, static)
        save(f, img)
        print(f"[mpm] cuadro {f}")
        if ONLY and f >= max(ONLY):
            break

    ev = {"duration_s": FRAMES / FPS, "fps": FPS, "n": int(n), "verify": ver,
          "shown": shown, "t_snow": T_SNOW, "t_sand": T_SAND, "t_gate": T_GATE,
          "t_tilt": TILT[1][0]}
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    with open(EVENTS, "w", encoding="utf-8") as fh:
        json.dump(ev, fh)


if __name__ == "__main__":
    main()
