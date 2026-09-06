import numpy as np, os
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = np.load(os.path.join(repo, "data", "shorts_curl_simcache.npz"), allow_pickle=True)
pos = d["positions"]  # (FRAMES, N, 3)
print("shape", pos.shape, "dtype", pos.dtype)
print("NaN total:", int(np.isnan(pos).sum()), " Inf total:", int(np.isinf(pos).sum()))
print()
print(f"{'frame':>5} {'nan':>5} {'inf':>5} {'maxabs':>10}")
for f in range(805, 825):
    fr = pos[f]
    finite = fr[np.isfinite(fr)]
    mx = float(np.max(np.abs(finite))) if finite.size else float("nan")
    print(f"{f:5d} {int(np.isnan(fr).sum()):5d} {int(np.isinf(fr).sum()):5d} {mx:10.3f}")
print()
bad = [f for f in range(pos.shape[0]) if not np.isfinite(pos[f]).all()]
print("Primer frame con NaN/inf:", (bad[0] if bad else "ninguno"), " | total frames afectados:", len(bad))
if bad:
    print("Frames afectados (primeros 20):", bad[:20])

# Segmentos degenerados en la ventana de estela del frame 810
TRAIL = 30
f = 810; lo = max(0, f - TRAIL + 1)
win = pos[lo:f + 1]  # (L, N, 3)
diffs = np.linalg.norm(np.diff(win.astype(np.float64), axis=0), axis=2)  # (L-1, N)
fin = win[np.isfinite(win)]
print()
print("Ventana estela frame 810:", win.shape)
print("  min dist consecutiva:", float(np.nanmin(diffs)), "(0 => puntos coincidentes)")
print("  segmentos < 1e-6:", int((diffs < 1e-6).sum()))
print("  maxabs en ventana:", (float(np.max(np.abs(fin))) if fin.size else "NaN"))
