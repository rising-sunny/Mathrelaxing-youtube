import subprocess, sys, os, time

REPO = os.path.dirname(os.path.abspath(__file__))
MAX = 5
for attempt in range(1, MAX + 1):
    print(f"\n=== Intento {attempt}/{MAX} ===")
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", "shorts_lorenz",
        "--scene", "scenes/lorenz_flow_numpy.py",
        "--attractor", "lorenz",
        "--engine", "numpy",
        "--frames", "900",
        "--res", "1024",
        "--samples", "32",
        "--fps", "60",
        "--format", "9:16",
        "--math-overlay",
        "--waveform"
    ])
    if r.returncode == 0:
        print("\n¡Listo!")
        break
    print(f"Crash en intento {attempt}, reintentando en 5s...")
    time.sleep(5)
