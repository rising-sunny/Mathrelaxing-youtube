import os
import sys
import time
import subprocess
import json

ENV_PATH = r"G:\Mi unidad\Scripts Python\Video-Optimizer-multiplatform\.env"

def load_env():
    env = {}
    if not os.path.exists(ENV_PATH):
        sys.exit(f"No se encuentra {ENV_PATH}")
    with open(ENV_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env

def run_vast_cmd(cmd):
    # Runs vastai command and returns json
    print(f"› vastai {' '.join(cmd)}", flush=True)
    res = subprocess.run(["vastai"] + cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("ERROR:", res.stderr, flush=True)
        sys.exit(1)
    try:
        return json.loads(res.stdout)
    except:
        return res.stdout

def run_ssh(host, port, cmd):
    # -o StrictHostKeyChecking=no is important
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-p", str(port), f"root@{host}", cmd]
    print(f"› {cmd}", flush=True)
    # let it stream output to stdout
    subprocess.run(ssh_cmd, check=True)

def main():
    env = load_env()
    API_KEY = env.get("VAST_API_KEY")
    if not API_KEY:
        sys.exit("Falta VAST_API_KEY en .env")
    
    # 1. Set API key
    subprocess.run(["vastai", "set", "api-key", API_KEY], check=True)
    
    # 2. Search for cheapest RTX 3090
    print("[vast] Buscando ofertas (RTX 3090)...", flush=True)
    # We query for RTX 3090, ordered by dph
    offers = run_vast_cmd(["search", "offers", "gpu_name=RTX_3090 rentable=True", "-o", "dph", "--raw"])
    if not offers:
        sys.exit("No se encontraron ofertas libres.")
    
    best_offer = offers[0]
    ask_id = best_offer["id"]
    gpu_name = best_offer["gpu_name"]
    print(f"[vast] Mejor oferta encontrada: ID {ask_id} ({gpu_name}) - ${best_offer['dph_total']:.3f}/h", flush=True)
    
    # 3. Create instance
    print(f"[vast] Creando instancia temporal...", flush=True)
    # image ubuntu:22.04, disk 25GB
    create_res = run_vast_cmd(["create", "instance", str(ask_id), "--image", "ubuntu:22.04", "--disk", "25", "--raw"])
    if "new_contract" not in create_res:
        sys.exit(f"Fallo al crear instancia: {create_res}")
        
    instance_id = create_res["new_contract"]
    print(f"[vast] Instancia alquilada y creada exitosamente con ID {instance_id}", flush=True)
    
    # 4. Wait for running status and SSH
    host = None
    port = None
    print("[vast] Esperando a que inicie la máquina virtual y abra puerto SSH...", flush=True)
    while True:
        info = run_vast_cmd(["show", "instances", "--raw"])
        inst = next((i for i in info if str(i["id"]) == str(instance_id)), None)
        if inst:
            actual = inst.get('actual_status')
            print(f"[vast] Estado: {actual}", flush=True)
            if actual == "running" and inst.get("ssh_port"):
                host = inst["ssh_host"]
                port = inst["ssh_port"]
                break
        time.sleep(10)
    
    print(f"[vast] Instancia completamente operativa en {host}:{port}", flush=True)
    print("[vast] Esperando 15s extra para que el demonio SSH inicialice...", flush=True)
    time.sleep(15)
    
    # 5. Setup & Render
    try:
        # Install deps and download blender
        setup_cmd = (
            "apt-get update -y && DEBIAN_FRONTEND=noninteractive apt-get install -y wget xz-utils libx11-6 libxi6 libxrender1 libxxf86vm1 libgl1-mesa-glx libxkbcommon-x11-0 libsm6 && "
            "if [ ! -d blender-4.4.3-linux-x64 ]; then "
            "echo 'Descargando Blender 4.4...'; "
            "wget -q https://download.blender.org/release/Blender4.4/blender-4.4.3-linux-x64.tar.xz; "
            "tar -xf blender-4.4.3-linux-x64.tar.xz; "
            "rm blender-4.4.3-linux-x64.tar.xz; "
            "fi; "
            "mkdir -p MathRelaxing/scenes MathRelaxing/output/cloud MathRelaxing/data"
        )
        print("[vast] Ejecutando Setup remoto y bajando Blender...", flush=True)
        run_ssh(host, port, setup_cmd)
        
        print("[vast] Subiendo archivo de la escena scenes/lorenz_attractor.py...", flush=True)
        subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port), "scenes/lorenz_attractor.py", f"root@{host}:MathRelaxing/scenes/lorenz_attractor.py"], check=True)
        
        print(f"[vast] ¡Iniciando render de Cycles (1080p) en {gpu_name} en la nube!", flush=True)
        render_cmd = (
            "cd MathRelaxing && "
            "../blender-4.4.3-linux-x64/blender --background --python scenes/lorenz_attractor.py -- "
            "--engine cycles --frames 360 --res 1080 --samples 64 --name lorenz"
        )
        run_ssh(host, port, render_cmd)
        
        print("[vast] Render finalizado. Descargando resultados (PNGs y JSON)...", flush=True)
        os.makedirs("output/cloud/frames", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port), "-r", f"root@{host}:MathRelaxing/output/lorenz/frames/*", "output/cloud/frames/"], check=True)
        subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port), f"root@{host}:MathRelaxing/data/lorenz_events.json", "data/cloud_events.json"], check=True)
        
    finally:
        # 6. Destroy instance NO MATTER WHAT, so we don't leak money.
        print(f"[vast] PROCESO TERMINADO. Destruyendo instancia {instance_id} para no generar cobros extras...", flush=True)
        run_vast_cmd(["destroy", "instance", str(instance_id)])
        print("[vast] Instancia destruida exitosamente.", flush=True)

if __name__ == "__main__":
    main()
