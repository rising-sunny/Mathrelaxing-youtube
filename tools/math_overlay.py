import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt

# Make math text look like true LaTeX (Computer Modern)
plt.rcParams['mathtext.fontset'] = 'cm'
plt.rcParams['font.family'] = 'serif'

# --- LORENZ ---
def velocity_lorenz(P, SCALE, OFFSET_Z, SIGMA, RHO, BETA):
    P_real = P / SCALE
    P_real[:, 2] -= OFFSET_Z
    x, y, z = P_real[:, 0], P_real[:, 1], P_real[:, 2]
    dx = SIGMA * (y - x)
    dy = x * (RHO - z) - y
    dz = x * y - BETA * z
    return np.stack([dx, dy, dz], axis=1) * SCALE

def rk4_lorenz(P, dt, SCALE, OFFSET_Z, SIGMA, RHO, BETA):
    k1 = velocity_lorenz(P, SCALE, OFFSET_Z, SIGMA, RHO, BETA)
    k2 = velocity_lorenz(P + 0.5 * dt * k1, SCALE, OFFSET_Z, SIGMA, RHO, BETA)
    k3 = velocity_lorenz(P + 0.5 * dt * k2, SCALE, OFFSET_Z, SIGMA, RHO, BETA)
    k4 = velocity_lorenz(P + dt * k3, SCALE, OFFSET_Z, SIGMA, RHO, BETA)
    return P + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

# --- ROSSLER ---
def velocity_rossler(P, SCALE, OFFSET_Z, A, B, C):
    P_real = P / SCALE
    P_real[:, 2] -= OFFSET_Z
    x, y, z = P_real[:, 0], P_real[:, 1], P_real[:, 2]
    dx = -y - z
    dy = x + A * y
    dz = B + z * (x - C)
    return np.stack([dx, dy, dz], axis=1) * SCALE

def rk4_rossler(P, dt, SCALE, OFFSET_Z, A, B, C):
    k1 = velocity_rossler(P, SCALE, OFFSET_Z, A, B, C)
    k2 = velocity_rossler(P + 0.5 * dt * k1, SCALE, OFFSET_Z, A, B, C)
    k3 = velocity_rossler(P + 0.5 * dt * k2, SCALE, OFFSET_Z, A, B, C)
    k4 = velocity_rossler(P + dt * k3, SCALE, OFFSET_Z, A, B, C)
    return P + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

# --- THOMAS ---
def velocity_thomas(P, SCALE, OFFSET_Z, B_VAL):
    P_real = P / SCALE
    P_real[:, 2] -= OFFSET_Z
    x, y, z = P_real[:, 0], P_real[:, 1], P_real[:, 2]
    dx = np.sin(y) - B_VAL * x
    dy = np.sin(z) - B_VAL * y
    dz = np.sin(x) - B_VAL * z
    return np.stack([dx, dy, dz], axis=1) * SCALE

def rk4_thomas(P, dt, SCALE, OFFSET_Z, B_VAL):
    k1 = velocity_thomas(P, SCALE, OFFSET_Z, B_VAL)
    k2 = velocity_thomas(P + 0.5 * dt * k1, SCALE, OFFSET_Z, B_VAL)
    k3 = velocity_thomas(P + 0.5 * dt * k2, SCALE, OFFSET_Z, B_VAL)
    k4 = velocity_thomas(P + dt * k3, SCALE, OFFSET_Z, B_VAL)
    return P + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

# --- DOUBLE PENDULUM ---
def velocity_pendulum(S, G_ACC=9.81):
    t1, t2, w1, w2 = S[:, 0], S[:, 1], S[:, 2], S[:, 3]
    d = t1 - t2
    den = 3.0 - np.cos(2 * d)
    a1 = (-3*G_ACC*np.sin(t1) - G_ACC*np.sin(t1-2*t2)
          - 2*np.sin(d)*(w2**2 + w1**2*np.cos(d))) / den
    a2 = (2*np.sin(d)*(2*w1**2 + 2*G_ACC*np.cos(t1)
          + w2**2*np.cos(d))) / den
    return np.stack([w1, w2, a1, a2], axis=1)

def rk4_pendulum(S, dt, G_ACC=9.81):
    k1 = velocity_pendulum(S, G_ACC)
    k2 = velocity_pendulum(S + 0.5*dt*k1, G_ACC)
    k3 = velocity_pendulum(S + 0.5*dt*k2, G_ACC)
    k4 = velocity_pendulum(S + dt*k3, G_ACC)
    return S + (dt/6.0)*(k1 + 2*k2 + 2*k3 + k4)

# --- GRAVITY N-BODY ---
def velocity_gravity(P, SCALE, M_pos, M_mass):
    pos = P[:, :3] / SCALE
    v = P[:, 3:] / SCALE
    acc = np.zeros_like(pos)
    for j in range(3):
        r_vec = (M_pos[j] / SCALE) - pos
        r_sq = np.sum(r_vec**2, axis=1, keepdims=True)
        r_mag = np.sqrt(r_sq + 1.0)
        acc += (M_mass[j] / SCALE / (r_mag**3)) * r_vec
    acc -= 0.1 * v
    return np.concatenate([v, acc], axis=1) * SCALE

def rk4_gravity(P, dt, SCALE, M_pos, M_mass):
    k1 = velocity_gravity(P, SCALE, M_pos, M_mass)
    k2 = velocity_gravity(P + 0.5 * dt * k1, SCALE, M_pos, M_mass)
    k3 = velocity_gravity(P + 0.5 * dt * k2, SCALE, M_pos, M_mass)
    k4 = velocity_gravity(P + dt * k3, SCALE, M_pos, M_mass)
    return P + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

# --- TOKAMAK FLOW ---
def velocity_tokamak(P, R0=3.0, B_toroidal=1.0, B_poloidal=0.3):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    rho = np.sqrt(x**2 + y**2) + 1e-5
    phi_x, phi_y, phi_z = -y/rho, x/rho, np.zeros_like(x)
    r_core_x, r_core_y, r_core_z = x*(1-R0/rho), y*(1-R0/rho), z
    pol_x = phi_y * r_core_z - phi_z * r_core_y
    pol_y = phi_z * r_core_x - phi_x * r_core_z
    pol_z = phi_x * r_core_y - phi_y * r_core_x
    pol_mag = np.sqrt(pol_x**2 + pol_y**2 + pol_z**2) + 1e-5
    vx = B_toroidal * phi_x + B_poloidal * pol_x/pol_mag
    vy = B_toroidal * phi_y + B_poloidal * pol_y/pol_mag
    vz = B_toroidal * phi_z + B_poloidal * pol_z/pol_mag
    return np.stack([vx, vy, vz], axis=1)

def rk4_tokamak(P, dt, R0=3.0):
    k1 = velocity_tokamak(P, R0)
    k2 = velocity_tokamak(P + 0.5 * dt * k1, R0)
    k3 = velocity_tokamak(P + 0.5 * dt * k2, R0)
    k4 = velocity_tokamak(P + dt * k3, R0)
    return P + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

# --- ABC FLOW ---
def velocity_abc(P, SCALE, A_P, B_P, C_P, t_val=0.0):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    A = A_P * (1.0 + 0.1 * np.sin(0.3 * t_val))
    B = B_P * (1.0 + 0.1 * np.cos(0.2 * t_val))
    C = C_P * (1.0 + 0.1 * np.sin(0.15 * t_val))
    vx = A * np.sin(z) + C * np.cos(y)
    vy = B * np.sin(x) + A * np.cos(z)
    vz = C * np.sin(y) + B * np.cos(x)
    return np.stack([vx, vy, vz], axis=1)

def rk4_abc(P, dt, SCALE, A_P, B_P, C_P, t_val=0.0):
    k1 = velocity_abc(P, SCALE, A_P, B_P, C_P, t_val)
    k2 = velocity_abc(P + 0.5 * dt * k1, SCALE, A_P, B_P, C_P, t_val + 0.5 * dt)
    k3 = velocity_abc(P + 0.5 * dt * k2, SCALE, A_P, B_P, C_P, t_val + 0.5 * dt)
    k4 = velocity_abc(P + dt * k3, SCALE, A_P, B_P, C_P, t_val + dt)
    return P + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

def simulate_and_draw(frames, outdir, res_w, res_h, fps=24, attractor="lorenz", name=None):
    N = 1000
    SEED_RADIUS = 0.1
    FPS = fps
    rng = np.random.default_rng(42)

    if attractor == "lorenz":
        SPEED = 0.4
        DT = SPEED / FPS
        SIGMA, RHO, BETA = 10.0, 28.0, 8.0 / 3.0
        SCALE, OFFSET_Z = 0.15, -25.0
        
        P0 = np.array([1.0, 1.0, 20.0]) * SCALE
        P0[2] += OFFSET_Z * SCALE
        
        formula_text = (
            r"$\frac{dx}{dt} = \sigma(y - x)$" + "\n\n" +
            r"$\frac{dy}{dt} = x(\rho - z) - y$" + "\n\n" +
            r"$\frac{dz}{dt} = xy - \beta z$"
        )
    elif attractor == "rossler":
        SPEED = 0.6
        DT = SPEED / FPS
        A, B, C = 0.2, 0.2, 5.7
        SCALE, OFFSET_Z = 0.25, 0.0
        
        P0 = np.array([10.0, 0.0, 0.0]) * SCALE
        P0[2] += OFFSET_Z * SCALE
        SEED_RADIUS = 0.01 * SCALE
        
        formula_text = (
            r"$\frac{dx}{dt} = -y - z$" + "\n\n" +
            r"$\frac{dy}{dt} = x + a y$" + "\n\n" +
            r"$\frac{dz}{dt} = b + z(x - c)$"
        )
    elif attractor == "thomas":
        SPEED = 0.5
        DT = SPEED / FPS
        B_val = 0.208186
        SCALE, OFFSET_Z = 0.5, 0.0
        
        P0 = np.array([1.0, 1.0, 1.0]) * SCALE
        P0[2] += OFFSET_Z * SCALE
        SEED_RADIUS = 0.1 * SCALE
        
        formula_text = (
            r"$\frac{dx}{dt} = \sin(y) - bx$" + "\n\n" +
            r"$\frac{dy}{dt} = \sin(z) - by$" + "\n\n" +
            r"$\frac{dz}{dt} = \sin(x) - bz$"
        )
    elif attractor == "pendulum":
        SPEED = 1.0
        DT = SPEED / FPS
        G_ACC_p = 9.81
        SCALE, OFFSET_Z = 1.0, 0.0
        SUBSTEPS_P = 2
        DT_SUB = DT / SUBSTEPS_P
        
        formula_text = (
            r"$\ddot{\theta}_1 = \frac{-g(2m_1+m_2)\sin\theta_1 - ...}{L_1 D}$" + "\n\n" +
            r"$\ddot{\theta}_2 = \frac{2\sin(\Delta)(...)}{L_2 D}$" + "\n\n" +
            r"$D = 2m_1+m_2-m_2\cos(2\Delta)$"
        )
        
        # State: (N, 4) = [theta1, theta2, omega1, omega2]
        S_pend = np.zeros((N, 4), dtype=np.float64)
        S_pend[:, 0] = 3*np.pi/4
        S_pend[:, 1] = 3*np.pi/4 + rng.normal(0, 1e-3, N)

    elif attractor == "gravity":
        SPEED = 1.0
        DT = SPEED / FPS
        SCALE, OFFSET_Z = 0.5, 0.0
        M_pos = np.array([[5.0, 5.0, 0.0], [-5.0, 5.0, 0.0], [0.0, -5.0, 0.0]]) * SCALE
        M_mass = np.array([150.0, 150.0, 150.0]) * SCALE
        
        P0 = np.array([0.0, 0.0, 5.0]) * SCALE
        SEED_RADIUS = 2.0 * SCALE
        
        formula_text = (
            r"$\vec{F} = \sum_i G \frac{M_i m}{|\vec{r}_i|^2} \hat{r}_i$" + "\n\n" +
            r"$\frac{d\vec{v}}{dt} = \vec{F} / m - \gamma \vec{v}$"
        )

    elif attractor == "curl":
        SPEED = 0.35
        DT = SPEED / FPS
        SCALE, OFFSET_Z = 1.0, 0.0
        NOISE_FREQ_O = 0.6
        TIME_SPEED_O = 0.15
        
        formula_text = (
            r"$\vec{v} = \nabla \times \vec{\Psi}(\vec{r}, t)$" + "\n\n" +
            r"$v_x = \frac{\partial \Psi_z}{\partial y} - \frac{\partial \Psi_y}{\partial z}$" + "\n\n" +
            r"$\nabla \cdot \vec{v} = 0$"
        )
        
        def curl_psi_o(x, y, z, t_val, comp=0):
            s = comp * 17.31 + 31.7
            return (np.sin((x * NOISE_FREQ_O + t_val * TIME_SPEED_O) + s)
                    * np.cos((y * NOISE_FREQ_O + t_val * TIME_SPEED_O * 0.7) * 1.3 + s * 0.37)
                    * np.sin((z * NOISE_FREQ_O + t_val * TIME_SPEED_O * 0.5) * 0.9 + s * 0.71)
                    + 0.5 * np.sin((x * NOISE_FREQ_O * 1.7 + y * NOISE_FREQ_O * 0.9 + t_val * TIME_SPEED_O * 1.3) + s * 1.13)
                          * np.cos((z * NOISE_FREQ_O * 1.4 + t_val * TIME_SPEED_O * 0.3) + s * 0.53))

        def curl_vel_o(pos, t_val):
            x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
            e = 0.01
            vx = ((curl_psi_o(x, y+e, z, t_val, 2) - curl_psi_o(x, y-e, z, t_val, 2))
                - (curl_psi_o(x, y, z+e, t_val, 1) - curl_psi_o(x, y, z-e, t_val, 1))) / (2*e)
            vy = ((curl_psi_o(x, y, z+e, t_val, 0) - curl_psi_o(x, y, z-e, t_val, 0))
                - (curl_psi_o(x+e, y, z, t_val, 2) - curl_psi_o(x-e, y, z, t_val, 2))) / (2*e)
            vz = ((curl_psi_o(x+e, y, z, t_val, 1) - curl_psi_o(x-e, y, z, t_val, 1))
                - (curl_psi_o(x, y+e, z, t_val, 0) - curl_psi_o(x, y-e, z, t_val, 0))) / (2*e)
            return np.stack([vx, vy, vz], axis=1)
        
        P_curl_o = rng.normal(0, 0.8, (N, 3))
    
    elif attractor == "chladni":
        SCALE, OFFSET_Z = 1.0, 0.0
        formula_text = (
            r"$W(x,y) = \sin(n \pi x)\sin(m \pi y)$" + "\n\n" +
            r"$+ \sin(m \pi x)\sin(n \pi y)$"
        )
        import json
        events_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", f"{name or 'shorts_chladni'}_events.json")
        try:
            with open(events_file, "r") as f_json:
                chladni_meta = json.load(f_json)
                chladni_events = chladni_meta["events"]
        except Exception as e:
            print(f"No se pudo cargar el JSON de eventos chladni: {e}")
            chladni_events = [{"m": 1.0, "n": 1.0, "speed": 0.0}] * frames

    elif attractor == "chladni_melody":
        SCALE, OFFSET_Z = 1.0, 0.0
        formula_text = (
            r"$W = \cos(n \pi x)\cos(m \pi y)$" + "\n\n" +
            r"$- \cos(m \pi x)\cos(n \pi y)$"
        )
        import json
        events_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", f"{name or 'shorts_melody'}_events.json")
        try:
            with open(events_file, "r") as f_json:
                chladni_meta = json.load(f_json)
                chladni_events = chladni_meta["events"]
        except Exception as e:
            print(f"No se pudo cargar el JSON de eventos chladni_melody: {e}")
            chladni_events = [{"m": 1.0, "n": 1.0, "speed": 0.0}] * frames

    elif attractor == "tokamak":
        SPEED = 0.5
        DT = SPEED / FPS
        N = 3500
        R0 = 3.0
        SCALE, OFFSET_Z = 1.0, 0.0
        B_T = 1.0
        B_P = 0.3
        
        formula_text = (
            r"Tokamak Magnetic Bottle" + "\n\n" +
            r"$\mathbf{B} = B_T \hat{\phi} + B_P \hat{\theta}$" + "\n\n" +
            r"$B_T \sim 1/r, \quad B_P \sim I_{plasma}$" + "\n\n" +
            r"$\hat{\phi}$: Toroidal direction" + "\n\n" +
            r"$\hat{\theta}$: Poloidal direction"
        )
        
        P_tok_o = rng.normal(0, 1.0, (N, 3))
        P_tok_o[:, 0] += R0

    elif attractor == "abc":
        SPEED = 0.3
        DT = SPEED / FPS
        SCALE, OFFSET_Z = 1.0, 0.0
        A_P_o, B_P_o, C_P_o = np.sqrt(3), np.sqrt(2), 1.0
        
        formula_text = (
            r"$v_x = A\sin(z) + C\cos(y)$" + "\n\n" +
            r"$v_y = B\sin(x) + A\cos(z)$" + "\n\n" +
            r"$v_z = C\sin(y) + B\cos(x)$"
        )
        
        P_abc_o = rng.uniform(0, 2 * np.pi, (N, 3))

    elif attractor == "reaction_diffusion":
        SCALE, OFFSET_Z = 1.0, 0.0
        formula_text = (
            r"$\frac{\partial A}{\partial t} = D_A \nabla^2 A - AB^2 + f(1 - A)$" + "\n\n" +
            r"$\frac{\partial B}{\partial t} = D_B \nabla^2 B + AB^2 - (k + f)B$"
        )
        import json
        events_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", f"{name or 'shorts_reaction'}_events.json")
        try:
            with open(events_file, "r") as f_json:
                react_meta = json.load(f_json)
                react_events = react_meta["events"]
        except Exception as e:
            print(f"No se pudo cargar el JSON de eventos reaction: {e}")
            react_events = [{"feed": 0.055, "kill": 0.062, "B_total": 0.0}] * frames

    if attractor == "pendulum":
        pass  # S_pend already initialized above
    elif attractor in ["curl", "chladni", "reaction_diffusion", "chladni_melody", "abc", "tokamak"]:
        pass  # Already initialized above or not needed
    elif attractor == "gravity":
        P_pos = P0 + rng.normal(size=(N, 3)) * SEED_RADIUS
        P_vel = rng.normal(size=(N, 3)) * (1.0 * SCALE)
        P = np.concatenate([P_pos, P_vel], axis=1)
    else:
        P = P0 + rng.normal(size=(N, 3)) * SEED_RADIUS
    os.makedirs(outdir, exist_ok=True)
    
    dpi = 100
    fig = plt.figure(figsize=(res_w/dpi, res_h/dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis('off')
    
    t_form = ax.text(0.5, 0.82, formula_text, fontsize=24, ha='center', va='center', color='white')
    t_vals = ax.text(0.5, 0.20, "", fontsize=18, ha='center', va='center', color='#ffcc00')
    
    print(f"[math_overlay] Generando {frames} imágenes PNG para {attractor}...")
    
    for f in range(frames):
        if attractor == "pendulum":
            tip_x = np.sin(S_pend[:, 0]) + np.sin(S_pend[:, 1])
            tip_y = -np.cos(S_pend[:, 0]) - np.cos(S_pend[:, 1])
            com = np.array([np.nanmean(tip_x), 0, np.nanmean(tip_y)])
        elif attractor == "curl":
            com = np.nanmean(P_curl_o, axis=0)
        elif attractor in ["chladni", "reaction_diffusion", "chladni_melody", "abc", "tokamak"]:
            com = np.array([0.0, 0.0, 0.0]) # No COM needed
        else:
            pos = P[:, :3] if P.shape[1] == 6 else P
            com = np.nanmean(pos, axis=0)
            
        com_real = com / SCALE
        com_real[2] -= OFFSET_Z
        rx, ry, rz = com_real
        
        if attractor == "lorenz":
            dx = SIGMA * (ry - rx)
            dy = rx * (RHO - rz) - ry
            dz = rx * ry - BETA * rz
            val_str = (
                rf"$(x, y, z) = ({rx:6.2f}, {ry:6.2f}, {rz:6.2f})$" + "\n\n" +
                rf"$(\frac{{dx}}{{dt}}, \frac{{dy}}{{dt}}, \frac{{dz}}{{dt}}) = ({dx:7.2f}, {dy:7.2f}, {dz:7.2f})$" + "\n\n" +
                r"$(\sigma, \rho, \beta) = (10.0, 28.0, 2.67)$"
            )
            P = rk4_lorenz(P, DT, SCALE, OFFSET_Z, SIGMA, RHO, BETA)
        elif attractor == "rossler":
            dx = -ry - rz
            dy = rx + A * ry
            dz = B + rz * (rx - C)
            val_str = (
                rf"$(x, y, z) = ({rx:6.2f}, {ry:6.2f}, {rz:6.2f})$" + "\n\n" +
                rf"$(\frac{{dx}}{{dt}}, \frac{{dy}}{{dt}}, \frac{{dz}}{{dt}}) = ({dx:7.2f}, {dy:7.2f}, {dz:7.2f})$" + "\n\n" +
                r"$(a, b, c) = (0.2, 0.2, 5.7)$"
            )
            P = rk4_rossler(P, DT, SCALE, OFFSET_Z, A, B, C)
        elif attractor == "thomas":
            dx = np.sin(ry) - B_val * rx
            dy = np.sin(rz) - B_val * ry
            dz = np.sin(rx) - B_val * rz
            val_str = (
                rf"$(x, y, z) = ({rx:6.2f}, {ry:6.2f}, {rz:6.2f})$" + "\n\n" +
                rf"$(\frac{{dx}}{{dt}}, \frac{{dy}}{{dt}}, \frac{{dz}}{{dt}}) = ({dx:7.2f}, {dy:7.2f}, {dz:7.2f})$" + "\n\n" +
                rf"$b = {B_val:6.4f}$"
            )
            P = rk4_thomas(P, DT, SCALE, OFFSET_Z, B_val)
        elif attractor == "pendulum":
            t1_m = np.mean(S_pend[:, 0])
            t2_m = np.mean(S_pend[:, 1])
            w1_m = np.mean(S_pend[:, 2])
            w2_m = np.mean(S_pend[:, 3])
            # Divergence metric
            tip_x = np.sin(S_pend[:, 0]) + np.sin(S_pend[:, 1])
            tip_y = -np.cos(S_pend[:, 0]) - np.cos(S_pend[:, 1])
            sigma_div = float(np.std(tip_x) + np.std(tip_y))
            
            # Musical note matching build_audio.py
            idx_float = (rz + 2.0) * 3.0
            idx = int(np.clip(np.round(idx_float), 0, 13))
            notes = ["C3", "D3", "E3", "G3", "A3", "C4", "D4", "E4", "G4", "A4", "C5", "D5", "E5", "G5"]
            current_note = notes[idx]
            
            val_str = (
                rf"$(\theta_1, \theta_2) = ({t1_m:6.3f}, {t2_m:6.3f})$" + "\n\n" +
                rf"$(\dot{{\theta}}_1, \dot{{\theta}}_2) = ({w1_m:6.2f}, {w2_m:6.2f})$" + "\n\n" +
                rf"$\sigma_{{div}} = {sigma_div:8.5f}$" + "\n\n" +
                rf"Note: {current_note}"
            )
            for _ in range(SUBSTEPS_P):
                S_pend = rk4_pendulum(S_pend, DT_SUB, G_ACC_p)
        elif attractor == "curl":
            t_val = f * DT
            vel_field = curl_vel_o(P_curl_o, t_val)
            mean_vel = np.nanmean(vel_field, axis=0)
            mean_speed = float(np.sqrt(np.sum(mean_vel**2)))
            com = np.nanmean(P_curl_o, axis=0)
            rx, ry, rz = com

            # Musical note (pentatonic, driven by speed)
            ratios = np.array([1.0, 1.122, 1.25, 1.5, 1.681, 2.0, 2.245, 2.5, 3.0, 3.363, 4.0, 4.49, 5.0, 6.0])
            notes_curl = ["G3", "A3", "B3", "D4", "E4", "G4", "A4", "B4", "D5", "E5", "G5", "A5", "B5", "D6"]
            idx_c = int(np.clip(np.round(mean_speed * 2.0), 0, 13))
            current_note = notes_curl[idx_c]

            val_str = (
                rf"$\vec{{r}}_{{com}} = ({rx:6.3f}, {ry:6.3f}, {rz:6.3f})$" + "\n\n" +
                rf"$|\vec{{v}}| = {mean_speed:6.4f}$" + "\n\n" +
                rf"Note: {current_note}"
            )
            P_curl_o = P_curl_o + DT * vel_field
            dist = np.sqrt(np.sum(P_curl_o**2, axis=1))
            mask = dist > 4.0
            if np.any(mask):
                P_curl_o[mask] *= (4.0 / dist[mask, np.newaxis]) * 0.95
        elif attractor == "tokamak":
            vel_field = velocity_tokamak(P_tok_o, R0)
            mean_vel = np.nanmean(vel_field, axis=0)
            mean_speed = float(np.sqrt(np.sum(mean_vel**2)))
            com = np.nanmean(P_tok_o, axis=0)
            rx, ry, rz = com
            
            dynamic_vals = (
                rf"$B_T = {B_T:.2f}, B_P = {B_P:.2f}$",
                rf"$R_0 = {R0:.2f}$",
                rf"$|\langle \mathbf{{v}} \rangle| = {mean_speed:.3f}$",
                rf"$\langle \mathbf{{r}} \rangle = ({rx:.1f}, {ry:.1f}, {rz:.1f})$",
                rf"$N = 3500$ particles"
            )
            val_str = "\n\n".join(dynamic_vals)
            P_tok_o = rk4_tokamak(P_tok_o, DT, R0)

        elif attractor == "abc":
            t_val = f * DT
            vel_field = velocity_abc(P_abc_o, SCALE, A_P_o, B_P_o, C_P_o, t_val)
            mean_vel = np.nanmean(vel_field, axis=0)
            mean_speed = float(np.sqrt(np.sum(mean_vel**2)))
            com = np.nanmean(P_abc_o, axis=0)
            rx, ry, rz = com
            
            A_cur = A_P_o * (1.0 + 0.1 * np.sin(0.3 * t_val))
            B_cur = B_P_o * (1.0 + 0.1 * np.cos(0.2 * t_val))
            C_cur = C_P_o * (1.0 + 0.1 * np.sin(0.15 * t_val))

            val_str = (
                rf"$(A, B, C) = ({A_cur:.3f}, {B_cur:.3f}, {C_cur:.3f})$" + "\n\n" +
                rf"$|\vec{{v}}| = {mean_speed:.4f}$" + "\n\n" +
                rf"$N = 3500$ particles"
            )
            P_abc_o = P_abc_o + DT * vel_field
            P_abc_o = P_abc_o % (2 * np.pi)
        elif attractor == "chladni" or attractor == "chladni_melody":
            ev = chladni_events[min(f, len(chladni_events)-1)]
            m, n, spd = ev.get("m", 1.0), ev.get("n", 1.0), ev.get("speed", 0.0)
            freq = 55.0 * (m**2 + n**2) / 2.0
            val_str = (
                rf"$\bf{{Mode:}}$ $(m = {m:.2f}, n = {n:.2f})$" + "\n\n" +
                rf"$\bf{{Mean Speed:}}$ {spd:.4f}" + "\n\n" +
                rf"$\bf{{Frequency:}}$ {freq:.1f} Hz"
            )
        elif attractor == "reaction_diffusion":
            ev = react_events[min(f, len(react_events)-1)]
            feed, kill = ev.get("feed", 0.0), ev.get("kill", 0.0)
            b_tot = ev.get("B_total", 0.0)
            val_str = (
                rf"$\bf{{Feed Rate (f):}}$ {feed:.4f}" + "\n\n" +
                rf"$\bf{{Kill Rate (k):}}$ {kill:.4f}" + "\n\n" +
                rf"$\bf{{Total B:}}$ {b_tot:.0f}"
            )
        elif attractor == "gravity":
            vel_mean = np.nanmean(P[:, 3:], axis=0) / SCALE
            vx, vy, vz = vel_mean
            spd = np.sqrt(vx**2 + vy**2 + vz**2)
            val_str = (
                rf"$\vec{{r}}_{{com}} = ({rx:6.2f}, {ry:6.2f}, {rz:6.2f})$" + "\n\n" +
                rf"$\vec{{v}}_{{com}} = ({vx:6.2f}, {vy:6.2f}, {vz:6.2f})$" + "\n\n" +
                rf"$|\vec{{v}}| = {spd:6.2f}$"
            )
            P = rk4_gravity(P, DT, SCALE, M_pos, M_mass)
            
        t_vals.set_text(val_str)
        
        path = os.path.join(outdir, f"{f:04d}.png")
        fig.savefig(path, transparent=True, facecolor='none', edgecolor='none')
        
        if (f+1) % 50 == 0:
            print(f"[math_overlay] {f+1}/{frames} completados...")
            
    plt.close(fig)
    print(f"[math_overlay] Listo. PNGs guardados en {outdir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=360)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--res-w", type=int, default=576)
    parser.add_argument("--res-h", type=int, default=1024)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--attractor", type=str, default="lorenz", choices=["lorenz", "rossler", "gravity", "thomas", "pendulum", "curl", "chladni", "reaction_diffusion", "chladni_melody", "abc", "tokamak"])
    parser.add_argument("--name", type=str, default=None)
    args = parser.parse_args()
    simulate_and_draw(args.frames, args.outdir, args.res_w, args.res_h, args.fps, args.attractor, args.name)
