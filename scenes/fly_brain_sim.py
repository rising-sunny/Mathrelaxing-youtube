"""
Simulador LIF sobre el conectoma real de la mosca (MaleCNS v1.0, FlyEM).

Mismo modelo y mismos parametros que Shiu et al., Nature 2024 (el modelo de
las simulaciones virales), reescrito en numpy para no depender de brian2:

    dv/dt = (v0 - v + g) / t_mbr          v0 = -52 mV,  t_mbr = 20 ms
    dg/dt = -g / tau                      tau = 5 ms
    v > v_th = -45 mV  ->  espiga;  v = v_rst = -52 mV,  g = 0;  2.2 ms refractario
    espiga de j -> g_i += w_ij  con retardo de 1.8 ms
    w_ij = signo(j) * sinapsis(j->i) * 0.275 mV
    signo: GABA y glutamato inhiben, el resto excita
    estimulo: Poisson a 150 Hz con peso 250 * 0.275 mV, sin refractario

La parte lineal se integra EXACTA en cada paso (no Euler): con g decayendo
como exponencial, v tiene solucion cerrada. Eso se comprueba en verify()
contra el potencial postsinaptico analitico y contra la frecuencia de
disparo analitica de una neurona con corriente constante.

Datos: FlyEM MaleCNS v1.0, Janelia Research Campus, licencia CC-BY.
"""
import math
import os

import numpy as np
import pandas as pd
import scipy.sparse as sp

V0, VRST, VTH = -52.0, -52.0, -45.0          # mV
TMBR, TAU = 20.0, 5.0                        # ms
TRFC, TDLY = 2.2, 1.8                        # ms
WSYN, FPOI, RPOI = 0.275, 250.0, 150.0       # mV, -, Hz
DT = 0.1                                     # ms

EM = math.exp(-DT / TMBR)
ES = math.exp(-DT / TAU)
# v(t+dt) - v0 = (v - v0) e^(-dt/tm) + g * K, con g decayendo en tau
K = TAU / (TMBR - TAU) * (EM - ES)
DLY = int(round(TDLY / DT))
RFC = int(round(TRFC / DT))


def step_linear(v, g):
    return V0 + (v - V0) * EM + g * K, g * ES


def verify():
    """1) el potencial postsinaptico sale igual a la formula cerrada;
    2) una neurona con corriente constante dispara a la frecuencia exacta."""
    # 1) PSP de una sola entrada de 1 mV
    n = 600
    v, g = V0, 1.0
    vs = []
    for _ in range(n):
        vs.append(v)
        v, g = step_linear(v, g)
    t = np.arange(n) * DT
    ana = V0 + TAU / (TMBR - TAU) * (np.exp(-t / TMBR) - np.exp(-t / TAU))
    psp_err = float(np.abs(np.array(vs) - ana).max())
    tpk = (TAU * TMBR / (TMBR - TAU)) * math.log(TMBR / TAU)
    tpk_sim = float(t[int(np.argmax(vs))])

    # 2) corriente constante: g fijo (tau infinito), umbral y refractario
    I = 12.0                                  # mV de empuje constante
    vinf = V0 + I
    isi = TRFC + TMBR * math.log((vinf - VRST) / (vinf - VTH))
    v, ref, spikes = VRST, 0, []
    for k in range(int(20000 / DT)):
        if ref > 0:
            ref -= 1
            continue
        v = V0 + (v - V0) * EM + I * (1 - EM)
        if v > VTH:
            spikes.append(k * DT)
            v, ref = VRST, RFC
    rate_sim = 1000.0 * (len(spikes) - 1) / (spikes[-1] - spikes[0])
    rate_ana = 1000.0 / isi
    rel = abs(rate_sim / rate_ana - 1)
    print(f"[fly] PSP contra formula cerrada: error {psp_err:.1e} mV, pico en "
          f"{tpk_sim:.1f} ms (exacto {tpk:.2f}) | corriente constante: "
          f"{rate_sim:.2f} Hz simulado vs {rate_ana:.2f} Hz analitico ({rel*100:.2f}%)")
    assert psp_err < 1e-9, f"el integrador no es exacto: {psp_err:.2e}"
    assert abs(tpk_sim - tpk) <= DT, "el pico del PSP no cae donde dice la formula"
    # el umbral se detecta al final del paso: el error por espiga es de un paso
    assert rel < DT / isi * 1.2, f"la frecuencia se aparta {rel*100:.2f}%"
    return {"psp_err": psp_err, "tpk": tpk, "rate_sim": rate_sim, "rate_ana": rate_ana}


def load(data_dir):
    """Red: neuronas del conectoma trazado, pesos con signo y posiciones."""
    w = pd.read_feather(os.path.join(
        data_dir, "connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather"),
        columns=["body_pre", "body_post", "weight"])
    bodies = np.union1d(w.body_pre.values, w.body_post.values)
    idx = pd.Series(np.arange(len(bodies)), index=bodies)

    nt = pd.read_feather(os.path.join(data_dir, "body-neurotransmitters-male-cns-v1.0.feather"),
                         columns=["body", "consensus_nt"]).set_index("body")["consensus_nt"]
    ntb = nt.reindex(bodies)
    inhib = ntb.isin(["gaba", "glutamate"]).values
    sign = np.where(inhib, -1.0, 1.0)

    pre = idx[w.body_pre.values].values
    post = idx[w.body_post.values].values
    val = w.weight.values.astype(np.float64) * WSYN * sign[pre]
    W = sp.csc_matrix((val, (post, pre)), shape=(len(bodies), len(bodies)))

    ann = pd.read_feather(os.path.join(data_dir, "body-annotations-male-cns-v1.0-minconf-0.5.feather"),
                          columns=["bodyId", "type", "mancType", "superclass", "somaLocation"])
    ann = ann.set_index("bodyId").reindex(bodies)
    stats = {"neurons": int(len(bodies)), "pairs": int(len(w)),
             "synapses": int(w.weight.sum()), "inhibitory": int(inhib.sum()),
             "nt_known": int(ntb.notna().sum())}
    return bodies, W, ann, stats


def ids_of(ann, bodies, types):
    t = ann["type"].astype(str).values
    mt = ann["mancType"].astype(str).values
    return np.nonzero(np.isin(t, types) | np.isin(mt, types))[0]


def simulate(W, stim, t_ms, rng, t_on=0.0, record=None):
    """Devuelve la lista de espigas (paso, neurona) y los paso en que ocurren."""
    n = W.shape[0]
    steps = int(round(t_ms / DT))
    v = np.full(n, V0)
    g = np.zeros(n)
    ref = np.zeros(n, np.int32)
    ring = np.zeros((DLY + 1, n))
    is_stim = np.zeros(n, bool)
    is_stim[stim] = True
    p_poi = RPOI * DT / 1000.0
    on = int(round(t_on / DT))
    spk_t, spk_i = [], []
    for k in range(steps):
        slot = k % (DLY + 1)
        g += ring[slot]
        ring[slot] = 0.0
        active = ref == 0
        v_new, g_new = step_linear(v, g)
        v = np.where(active, v_new, v)
        g = np.where(active, g_new, g)
        ref[~active] -= 1
        if k >= on:
            hit = stim[rng.random(len(stim)) < p_poi]
            v[hit] += WSYN * FPOI                    # el Poisson empuja directo
        fired = np.nonzero((v > VTH) & (active | is_stim))[0]
        if len(fired):
            v[fired] = VRST
            g[fired] = 0.0
            ref[fired] = np.where(is_stim[fired], 0, RFC)
            ring[(k + DLY) % (DLY + 1)] += np.asarray(W[:, fired].sum(axis=1)).ravel()
            spk_t.append(np.full(len(fired), k, np.int32))
            spk_i.append(fired.astype(np.int32))
    if spk_t:
        return np.concatenate(spk_t), np.concatenate(spk_i)
    return np.zeros(0, np.int32), np.zeros(0, np.int32)
