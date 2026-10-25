"""Renderer de la familia `expression` para /opt/mathrelaxing-auto.

Mismo contrato que renderer.py:
  python expression_renderer.py --recipe item.json --out DIR [--smoke]
Escribe DIR/short.mp4 (1080x1920, 30 fps, con audio) y DIR/validation.json.
"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from expressions import BY_ID  # noqa: E402

FONT_PATHS = {
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", str(HERE / "font.ttf")],
    "regular": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", str(HERE / "font.ttf")],
}


def font(kind, size):
    for p in FONT_PATHS[kind]:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- geometria

def param_at(expr, u):
    """Valor del parametro para u en [0, 1] de la fase de morph."""
    a0, a1 = expr["a"]
    if expr.get("pingpong"):
        u = 1 - abs(1 - 2 * u)
    a = a0 + (a1 - a0) * smooth(u)
    return round(a) if expr.get("a_int") else a


def curve(expr, a):
    n = expr.get("samples", 3000)
    s = np.linspace(*expr["domain"], n)
    with np.errstate(all="ignore"):
        if expr["kind"] == "polar":
            r = expr["f"](s, a)
            x, y = r * np.cos(s), r * np.sin(s)
        elif expr["kind"] == "param":
            x, y = expr["f"](s, a)
        else:
            x, y = s, expr["f"](s, a)
    x = np.asarray(x, float) + 0 * s
    y = np.asarray(y, float) + 0 * s
    bad = ~(np.isfinite(x) & np.isfinite(y))
    x[bad] = np.nan
    y[bad] = np.nan
    return x, y


class Mapper:
    """Coordenadas matematicas -> pixeles, con escala fija durante todo el video."""

    def __init__(self, expr, W, H):
        self.cart = expr["kind"] == "cartesian"
        if self.cart:
            x0, x1, y0, y1 = expr["view"]
            self.box = (0.07 * W, 0.25 * H, 0.93 * W, 0.66 * H)
        else:
            xs, ys = [], []
            for u in np.linspace(0, 1, 13):
                x, y = curve(expr, param_at(expr, u))
                xs.append(x)
                ys.append(y)
            xs, ys = np.concatenate(xs), np.concatenate(ys)
            x0, x1, y0, y1 = np.nanmin(xs), np.nanmax(xs), np.nanmin(ys), np.nanmax(ys)
            # Caja centrada que conserva la proporcion de la curva.
            bw, bh, cx, cy = 0.84 * W, 0.46 * H, 0.5 * W, 0.45 * H
            sc = min(bw / max(x1 - x0, 1e-9), bh / max(y1 - y0, 1e-9))
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            x0, x1 = mx - bw / 2 / sc, mx + bw / 2 / sc
            y0, y1 = my - bh / 2 / sc, my + bh / 2 / sc
            self.box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
        self.view = (x0, x1, y0, y1)

    def __call__(self, x, y):
        x0, x1, y0, y1 = self.view
        bx0, by0, bx1, by1 = self.box
        px = bx0 + (x - x0) / (x1 - x0) * (bx1 - bx0)
        py = by1 - (y - y0) / (y1 - y0) * (by1 - by0)
        if self.cart:
            # Fuera de la ventana: cortar el trazo en vez de dibujar lineas al infinito.
            span = by1 - by0
            off = (py < by0 - 0.15 * span) | (py > by1 + 0.15 * span)
            px, py = px.copy(), py.copy()
            px[off] = np.nan
            py[off] = np.nan
        return px, py


def runs(px, py, start, stop):
    """Tramos continuos (sin NaN) entre los indices start..stop."""
    ok = np.isfinite(px[start:stop])
    idx = np.flatnonzero(ok) + start
    if idx.size < 2:
        return []
    cuts = np.flatnonzero(np.diff(idx) > 1) + 1
    return [seg for seg in np.split(idx, cuts) if seg.size >= 2]


def draw_curve(draw, px, py, upto, colors, width, chunk):
    n = px.size
    upto = int(min(upto, n))
    for c0 in range(0, upto - 1, chunk):
        c1 = min(c0 + chunk + 1, upto)
        col = tuple(int(v) for v in colors[min(c0, n - 1)])
        for seg in runs(px, py, c0, c1):
            pts = list(zip(px[seg].tolist(), py[seg].tolist()))
            draw.line(pts, fill=col, width=width, joint="curve")


# -------------------------------------------------------------------- texto

def draw_centered(draw, text, y, fnt, fill, W):
    w = draw.textlength(text, font=fnt)
    draw.text(((W - w) / 2, y), text, font=fnt, fill=fill)


def fit_font(draw, text, kind, size, max_w):
    f = font(kind, size)
    while draw.textlength(text, font=f) > max_w and size > 18:
        size -= 2
        f = font(kind, size)
    return f


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


# ---------------------------------------------------------------- fondo/ejes

def background(W, H, palette):
    base = hex_rgb(palette[0])
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - 0.45 * H) / H) ** 2)
    glow = np.clip(1 - d * 1.6, 0, 1)[..., None] ** 2
    img = base + glow * (hex_rgb(palette[1]) * 0.10)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def draw_axes(draw, m, s, palette):
    x0, x1, y0, y1 = m.view
    bx0, by0, bx1, by1 = m.box
    grid = tuple(int(v) for v in hex_rgb(palette[1]) * 0.18)
    axis = tuple(int(v) for v in hex_rgb(palette[1]) * 0.45)
    for k in range(1, 8):
        gx = bx0 + (bx1 - bx0) * k / 8
        draw.line([(gx, by0), (gx, by1)], fill=grid, width=max(1, int(s)))
    for k in range(1, 6):
        gy = by0 + (by1 - by0) * k / 6
        draw.line([(bx0, gy), (bx1, gy)], fill=grid, width=max(1, int(s)))
    if y0 < 0 < y1:
        _, py = m(np.array([0.0]), np.array([0.0]))
        draw.line([(bx0, py[0]), (bx1, py[0])], fill=axis, width=max(2, int(2 * s)))
    if x0 < 0 < x1:
        px, _ = m(np.array([0.0]), np.array([0.0]))
        draw.line([(px[0], by0), (px[0], by1)], fill=axis, width=max(2, int(2 * s)))


# -------------------------------------------------------------------- audio

PROGRESSIONS = [  # semitonos sobre la tonica, 4 acordes
    [[0, 3, 7, 10, 14], [-4, 0, 3, 7], [3, 7, 10, 14], [-2, 2, 5, 9]],   # Cm9 Abmaj7 Ebmaj9 Bbadd9
    [[0, 4, 7, 11], [-3, 0, 4, 7], [5, 9, 12, 16], [7, 11, 14, 17]],     # Cmaj7 Am7 Fmaj7 G
    [[0, 3, 7, 10], [5, 8, 12, 15], [-2, 2, 5, 9], [3, 7, 10, 14]],      # Cm7 Fm7 Bb Ebmaj9
    [[0, 4, 7, 14], [-5, -1, 2, 7], [-3, 0, 4, 9], [5, 9, 12, 16]],      # Cadd9 G/B Am Fmaj7
]
PENTA = [0, 2, 4, 7, 9, 12, 14, 16]


def synth_audio(path, dur, seed, sr=48000):
    rng = np.random.default_rng(seed)
    n = int(round(dur * sr))
    t = np.arange(n) / sr
    root = 130.81 * 2 ** (rng.integers(-3, 3) / 12)  # alrededor de Do3
    prog = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    hz = lambda semi, base=root: base * 2 ** (semi / 12)
    out = np.zeros((2, n))
    seg = dur / len(prog)
    # Pad: acordes con ataque y salida suaves y leve desafinacion estereo.
    for i, chord in enumerate(prog):
        t0 = i * seg
        env = smooth((t - t0 + 0.8) / 1.6) * (1 - smooth((t - (t0 + seg) + 0.2) / 1.6))
        for semi in chord:
            f = hz(semi)
            for ch, det in ((0, 0.998), (1, 1.002)):
                out[ch] += env * 0.06 * (np.sin(2 * np.pi * f * det * t) + 0.3 * np.sin(4 * np.pi * f * det * t))
        out += env * 0.09 * np.sin(2 * np.pi * hz(chord[0], root / 2) * t)  # bajo redondo
    # Melodia tipo campana: motivo pentatonico, mayormente por grados.
    step, k, beat = 0, rng.integers(2, 5), 60 / 66
    for j in range(int(dur / beat) - 1):
        if rng.random() < 0.35:
            continue
        k = int(np.clip(k + rng.choice([-1, 1, 1, 2, -2]), 0, len(PENTA) - 1))
        f = hz(PENTA[k] + 12)
        t0 = 0.6 + j * beat
        m = t >= t0
        tt = t[m] - t0
        note = np.exp(-tt * 1.6) * (1 - np.exp(-tt * 60)) * (
            np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 2.01 * f * tt) + 0.08 * np.sin(2 * np.pi * 3 * f * tt))
        pan = 0.5 + 0.3 * np.sin(step)
        out[0, m] += 0.11 * note * (1 - pan)
        out[1, m] += 0.11 * note * pan
        step += 1.3
    # Reverb: convolucion con cola de ruido decreciente, distinta por canal.
    from scipy.signal import fftconvolve
    ir_t = np.arange(int(2.2 * sr)) / sr
    for ch in range(2):
        ir = rng.standard_normal(ir_t.size) * np.exp(-ir_t * 2.6)
        ir[0] = 0
        out[ch] = 0.78 * out[ch] + 0.22 * fftconvolve(out[ch], ir / np.sqrt((ir ** 2).sum()))[:n]
    fade = np.minimum(1, t / 0.3) * np.clip((dur - t) / 1.2, 0, 1)
    out *= fade
    rms = np.sqrt((out ** 2).mean()) or 1
    out *= 10 ** (-18 / 20) / rms
    peak = np.abs(out).max()
    if peak > 10 ** (-2 / 20):
        out *= 10 ** (-2 / 20) / peak
    pcm = (out.T * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- principal

def render(entry, out, smoke):
    rec = entry["recipe"]
    expr = BY_ID[rec["expression_id"]]
    fps, dur = rec.get("fps", 30), rec["duration_seconds"]
    W, H = rec.get("width", 1080), rec.get("height", 1920)
    s = 0.5 if smoke else 1.0  # smoke: resolucion interna reducida
    w, h = int(W * s), int(H * s)
    palette = rec["palette"]
    ov = rec["overlay"]
    count = int(round(dur * fps))

    out.mkdir(parents=True, exist_ok=True)
    audio = out / "audio.wav"
    synth_audio(audio, dur, rec["audio"]["seed"])

    m = Mapper(expr, w, h)
    bg = background(w, h, palette)
    if m.cart:
        draw_axes(ImageDraw.Draw(bg), m, s, palette)
        if expr.get("ref"):
            rx = np.linspace(*expr["domain"], 2000)
            px, py = m(rx, expr["ref"](rx))
            ref_col = tuple(int(v) for v in hex_rgb(palette[2]) * 0.35)
            draw_curve(ImageDraw.Draw(bg), px, py, px.size, [ref_col] * px.size, max(2, int(3 * s)), 200)

    c1, c2 = hex_rgb(palette[1]), hex_rgb(palette[2])
    n = expr.get("samples", 3000)
    u = np.linspace(0, 1, n)[:, None]
    colors = c1 * (1 - u) + c2 * u
    width = max(2, int(expr.get("width", 5) * s))
    chunk = max(8, n // 60)

    tmp = ImageDraw.Draw(bg)
    hook_f = font("bold", int(66 * s))
    hook_lines = wrap(tmp, ov["hook"], hook_f, 0.88 * w)
    eq_f = [fit_font(tmp, line, "regular", int(50 * s), 0.9 * w) for line in expr["label"]]
    eq_f = [min(eq_f, key=lambda f: f.size)] * len(eq_f)  # mismo tamano en todas las lineas
    val_f = font("bold", int(46 * s))
    cta_f = fit_font(tmp, ov["closing"], "bold", int(58 * s), 0.9 * w)
    handle_f = font("regular", int(40 * s))
    white = (240, 242, 248)
    accent = tuple(int(v) for v in c2)

    T_TRACE, M0, M1 = 0.52 * dur, 0.55 * dur, 0.86 * dur
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-framerate", str(fps), "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", "-movflags", "+faststart"]
    if (w, h) != (W, H):
        cmd += ["-vf", f"scale={W}:{H}:flags=lanczos"]
    video = out / "short.mp4"
    proc = subprocess.Popen(cmd + [str(video)], stdin=subprocess.PIPE)

    cache = {}
    for i in range(count):
        tsec = i / fps
        if tsec < M0:
            a, prog = expr["a"][0], smooth((tsec - 0.25) / (T_TRACE - 0.25))
        else:
            a, prog = param_at(expr, (tsec - M0) / (M1 - M0)), 1.0
        key = a if expr.get("a_int") else None
        if key is not None and key in cache:
            px, py = cache[key]
        else:
            px, py = m(*curve(expr, a))
            if key is not None:
                cache[key] = (px, py)
        upto = prog * n

        layer = Image.new("RGB", (w, h))
        draw_curve(ImageDraw.Draw(layer), px, py, upto, colors, width, chunk)
        small = layer.resize((w // 2, h // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(10 * s))
        glow = small.resize((w, h), Image.BILINEAR)
        frame = ImageChops.screen(bg, ImageChops.add(glow, glow))
        frame = ImageChops.screen(frame, layer)
        d = ImageDraw.Draw(frame)

        if 0 < prog < 1:  # cabeza brillante del trazo
            j = int(min(upto, n - 1))
            while j > 0 and not np.isfinite(px[j]):
                j -= 1
            if np.isfinite(px[j]):
                r = 9 * s
                d.ellipse([px[j] - r, py[j] - r, px[j] + r, py[j] + r], fill=(255, 255, 255))

        # Textos: gancho arriba, ecuacion y valor del parametro abajo, CTA al final.
        y = 0.075 * h
        for line in hook_lines:
            draw_centered(d, line, y, hook_f, white, w)
            y += hook_f.size * 1.18
        y = 0.70 * h
        for line, f in zip(expr["label"], eq_f):
            draw_centered(d, line, y, f, white, w)
            y += f.size * 1.35
        a_txt = f"{expr['a_name']} = {int(a)}" if expr.get("a_int") else f"{expr['a_name']} = {a:.2f}"
        draw_centered(d, a_txt, y + 10 * s, val_f, accent, w)
        if tsec > M1 - 0.4:
            alpha = smooth((tsec - (M1 - 0.4)) / 0.6)
            col = tuple(int(c * alpha) for c in accent)
            draw_centered(d, ov["closing"], 0.855 * h, cta_f, col, w)
        draw_centered(d, ov.get("handle", "@MathRelaxing"), 0.925 * h, handle_f, (150, 156, 170), w)

        fade = min(1.0, tsec / 0.4, (dur - tsec) / 0.5)
        if fade < 1:
            frame = Image.eval(frame, lambda v, f=max(fade, 0): int(v * f))
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg encode failed")
    audio.unlink()

    check = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"], capture_output=True, text=True)
    ok = check.returncode == 0 and not check.stderr.strip()
    (out / "validation.json").write_text(json.dumps({
        "preview": smoke, "frames": count, "fps": fps, "width": W, "height": H,
        "full_decode_passed": ok, "internal_resolution": [w, h], "expression_id": expr["id"]}))
    if not ok:
        raise RuntimeError("Decode check failed: " + check.stderr[:500])
    return video


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    print(render(json.loads(a.recipe.read_text()), a.out, a.smoke))


if __name__ == "__main__":
    main()
