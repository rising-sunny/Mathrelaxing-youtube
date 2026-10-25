"""Catalogo de 30 expresiones para el calendario diario de MathRelaxing.

Cada expresion se anima en dos fases: primero la curva se dibuja con el
parametro en `a[0]`, luego el parametro recorre `a` y la forma se transforma.

kind:
  polar      f(theta, a) -> r
  param      f(t, a)     -> (x, y)
  cartesian  f(x, a)     -> y        (requiere `view` = (x0, x1, y0, y1))
"""
import math

import numpy as np


def _sgnpow(v, p):
    return np.sign(v) * np.abs(v) ** p


def _fourier_square(x, n):
    k = np.arange(1, int(n) + 1)[:, None]
    return 4 / np.pi * (np.sin((2 * k - 1) * x) / (2 * k - 1)).sum(axis=0)


def _taylor_sin(x, n):
    k = np.arange(0, int(n) + 1)[:, None]
    fact = np.array([math.factorial(2 * int(i) + 1) for i in k.ravel()], dtype=float)[:, None]
    return ((-1.0) ** k * x ** (2 * k + 1) / fact).sum(axis=0)


def _weierstrass(x, n):
    k = np.arange(0, int(n) + 1)[:, None]
    return (0.5 ** k * np.cos(3.0 ** k * np.pi * x)).sum(axis=0)


def _takagi(x, n):
    k = np.arange(0, int(n) + 1)[:, None]
    s = 2.0 ** k * x
    return (np.abs(s - np.round(s)) / 2.0 ** k).sum(axis=0)


def _dirichlet(x, n):
    n = int(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.sin((n + 0.5) * x) / np.sin(x / 2)
    y = np.where(np.abs(x) < 1e-9, 2 * n + 1, y)
    return y / (2 * n + 1)


def _bessel(x, a):
    from scipy.special import jv
    return jv(a, x)


def _cassini(th, b):
    inner = np.sqrt(np.maximum(b ** 4 - np.sin(2 * th) ** 2, 0))
    return np.sqrt(np.maximum(np.cos(2 * th) + inner, 0))


def _z(z):
    return z.real, z.imag


TAU = 2 * np.pi

EXPRESSIONS = [
    # --- 1-10 ---
    dict(id="rose-7-4", kind="polar", f=lambda th, k: np.cos(k * th), domain=(0, 4 * TAU), a=(1.75, 2.25), a_name="k",
         label=["r = cos(k·θ)"],
         title="A 7/4 Rose Drawn by 1 Equation", hook="ONE FORMULA, ENDLESS PETALS",
         question="How many petals do you count?", desc="Polar rose r = cos(kθ) with a slowly changing k"),
    dict(id="spirograph", kind="param", domain=(0, 3 * TAU), a=(1.5, 4.5), a_name="d", pingpong=True,
         f=lambda t, d: (2 * np.cos(t) + d * np.cos(2 * t / 3), 2 * np.sin(t) - d * np.sin(2 * t / 3)),
         label=["x = 2·cos t + d·cos(2t/3)", "y = 2·sin t − d·sin(2t/3)"],
         title="The Spirograph Equation in 16 Seconds", hook="A SPIROGRAPH WRITTEN IN MATH",
         question="Which loop is your favorite?", desc="Hypotrochoid with a changing pen distance d"),
    dict(id="fourier-square", kind="cartesian", f=_fourier_square, domain=(-TAU, TAU), a=(1, 40), a_int=True, a_name="N",
         view=(-TAU, TAU, -1.6, 1.6), samples=4000,
         label=["y = 4/π · Σ sin((2n−1)x) / (2n−1)", "n = 1 … N"],
         title="40 Sine Waves Build a Perfect Square", hook="ADD SINE WAVES… GET A SQUARE?",
         question="Can you spot the overshoot at the edges?", desc="Fourier series of a square wave, adding one term at a time"),
    dict(id="butterfly", kind="polar", domain=(0, 6 * TAU), a=(2.0, 2.8), a_name="a", pingpong=True, samples=6000,
         f=lambda th, a: np.exp(np.sin(th)) - a * np.cos(4 * th) + np.sin((2 * th - np.pi) / 24) ** 5,
         label=["r = exp(sin θ) − a·cos(4θ)", "+ sin⁵((2θ − π)/24)"],
         title="The Butterfly Curve: 1 Equation, 12 Turns", hook="THIS BUTTERFLY IS AN EQUATION",
         question="Did you expect a formula to look this alive?", desc="Temple Fay's butterfly curve in polar coordinates"),
    dict(id="heart", kind="param", domain=(0, TAU), a=(3.0, 1.2), a_name="p", pingpong=True,
         f=lambda t, p: (16 * _sgnpow(np.sin(t), p), 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)),
         label=["x = 16·sinᵖ t", "y = 13cos t − 5cos 2t − 2cos 3t − cos 4t"],
         title="The Heart Equation with 4 Cosines", hook="A HEART MADE OF COSINES",
         question="Who would you send this equation to?", desc="Classic parametric heart curve with a changing exponent p"),
    dict(id="sinc", kind="cartesian", f=lambda x, a: np.sinc(a * x / np.pi), domain=(-20, 20), a=(0.6, 4.0), a_name="a", pingpong=True,
         view=(-20, 20, -0.45, 1.2),
         label=["y = sin(a·x) / (a·x)"],
         title="The Sinc Function Squeezed 6 Times", hook="THE WAVE THAT NEVER QUITE STOPS",
         question="Where does the wave reach zero?", desc="Normalized sinc function with a changing frequency a"),
    dict(id="limacon", kind="polar", f=lambda th, a: 1 + a * np.cos(th), domain=(0, TAU), a=(0.3, 2.0), a_name="a",
         label=["r = 1 + a·cos θ"],
         title="From Circle to Inner Loop with 1 Parameter", hook="WATCH A LOOP GROW INSIDE",
         question="At which value does the cardioid appear?", desc="Limaçon of Pascal: circle, cardioid and inner loop"),
    dict(id="farris-wheel", kind="param", domain=(0, TAU), a=(1 / 3, 0.6), a_name="c", pingpong=True, samples=5000,
         f=lambda t, c: _z(np.exp(1j * t) + 0.5 * np.exp(6j * t) + c * 1j * np.exp(-14j * t)),
         label=["z = exp(it) + ½·exp(6it)", "+ c·i·exp(−14it)"],
         title="3 Spinning Circles Draw This Pattern", hook="THREE CIRCLES, ONE SYMMETRY",
         question="How many symmetry axes can you find?", desc="Farris wheel: a sum of three rotating circles"),
    dict(id="taylor-sin", kind="cartesian", f=_taylor_sin, domain=(-3 * np.pi, 3 * np.pi), a=(0, 12), a_int=True, a_name="N",
         view=(-3 * np.pi, 3 * np.pi, -2.2, 2.2), ref=np.sin,
         label=["y = Σ (−1)ᵏ x²ᵏ⁺¹ / (2k+1)!", "k = 0 … N"],
         title="12 Polynomials Become a Sine Wave", hook="POLYNOMIALS PRETENDING TO BE SINE",
         question="How many terms until it fits?", desc="Taylor polynomials of sin(x) approaching the sine curve"),
    dict(id="rose-ripple", kind="polar", f=lambda th, a: np.sin(4 * th) + a * np.sin(12 * th), domain=(0, TAU), a=(0.0, 0.6),
         a_name="a", pingpong=True,
         label=["r = sin(4θ) + a·sin(12θ)"],
         title="8 Petals with Ripples from 1 Extra Term", hook="ONE TERM CHANGES EVERY PETAL",
         question="Which version do you prefer?", desc="Rose curve with an added higher harmonic"),
    # --- 11-20 ---
    dict(id="maurer-rose", kind="param", domain=(0, 360), samples=361, a=(71, 79), a_int=True, a_name="d", width=2.5,
         f=lambda k, d: (np.sin(6 * np.radians(k * d)) * np.cos(np.radians(k * d)),
                         np.sin(6 * np.radians(k * d)) * np.sin(np.radians(k * d))),
         label=["θₖ = k·d°,  r = sin(6·θₖ)", "k = 0 … 360"],
         title="361 Straight Lines Hide a Rose", hook="STRAIGHT LINES, CURVED FLOWER",
         question="Can you still see the rose?", desc="Maurer rose: straight segments jumping along a 6-petal rose"),
    dict(id="wave-packet", kind="cartesian", f=lambda x, a: np.exp(-x ** 2 / 2) * np.cos(a * x), domain=(-5, 5), a=(2, 12),
         a_name="ω", pingpong=True, view=(-5, 5, -1.2, 1.2),
         label=["y = exp(−x²/2)·cos(ω·x)"],
         title="A Wave Trapped Inside 1 Bell Curve", hook="A WAVE INSIDE A BELL",
         question="Where does the energy concentrate?", desc="Gaussian wave packet with a changing frequency ω"),
    dict(id="abs-cos-power", kind="polar", f=lambda th, p: np.abs(np.cos(3 * th)) ** p, domain=(0, TAU), a=(0.25, 3.0),
         a_name="p", pingpong=True,
         label=["r = |cos(3θ)|ᵖ"],
         title="6 Petals from Round to Sharp", hook="ROUND OR SHARP? ONE EXPONENT",
         question="Round petals or sharp ones?", desc="Rose curve raised to a changing power p"),
    dict(id="epicycloid", kind="param", domain=(0, 3 * TAU), a=(3.0, 5.0), a_name="k",
         f=lambda t, k: ((k + 1) * np.cos(t) - np.cos((k + 1) * t), (k + 1) * np.sin(t) - np.sin((k + 1) * t)),
         label=["x = (k+1)·cos t − cos((k+1)t)", "y = (k+1)·sin t − sin((k+1)t)"],
         title="A Circle Rolling Around 3 to 5 Cusps", hook="ROLL A CIRCLE AROUND A CIRCLE",
         question="How many cusps do you see at the end?", desc="Epicycloid traced by a point on a rolling circle"),
    dict(id="weierstrass", kind="cartesian", f=_weierstrass, domain=(-2, 2), a=(0, 6), a_int=True, a_name="N", samples=12000,
         view=(-2, 2, -2.2, 2.2), width=3,
         label=["y = Σ 0.5ⁿ·cos(3ⁿ·π·x)", "n = 0 … N"],
         title="A Curve with 0 Smooth Points", hook="CONTINUOUS EVERYWHERE, SMOOTH NOWHERE",
         question="Would you call this a curve?", desc="Partial sums of the Weierstrass function"),
    dict(id="nephroid-sin-half", kind="polar", f=lambda th, a: 1 + a * np.sin(th / 2), domain=(0, 2 * TAU), a=(2.0, 0.5),
         a_name="a", pingpong=True,
         label=["r = 1 + a·sin(θ/2)"],
         title="1 Half-Angle Makes a Double Loop", hook="HALF AN ANGLE, TWICE THE LOOP",
         question="Where do the loops cross?", desc="Polar curve with a half-angle sine"),
    dict(id="harmonograph", kind="param", domain=(0, 60), a=(0.0, np.pi / 2), a_name="φ", samples=8000,
         f=lambda t, ph: (np.exp(-0.03 * t) * np.sin(2 * t) + np.exp(-0.02 * t) * np.sin(3 * t + ph),
                          np.exp(-0.025 * t) * np.sin(2 * t + np.pi / 2) + np.exp(-0.015 * t) * np.sin(3 * t)),
         label=["x = e⁻⁰·⁰³ᵗ·sin 2t + e⁻⁰·⁰²ᵗ·sin(3t + φ)", "y = e⁻⁰·⁰²⁵ᵗ·cos 2t + e⁻⁰·⁰¹⁵ᵗ·sin 3t"],
         title="2 Pendulums Draw This Spiral", hook="TWO PENDULUMS, ONE DRAWING",
         question="Does it look like a seashell to you?", desc="Damped harmonograph with a changing phase φ"),
    dict(id="beats", kind="cartesian", f=lambda x, a: np.sin(10 * x) + np.sin(a * x), domain=(0, 20), a=(10.5, 11.5),
         a_name="ω", pingpong=True, view=(0, 20, -2.2, 2.2), samples=5000,
         label=["y = sin(10x) + sin(ω·x)"],
         title="2 Sine Waves Create Beats", hook="TWO WAVES, ONE HEARTBEAT",
         question="Can you hear the beats in your head?", desc="Interference of two close frequencies"),
    dict(id="offset-rose", kind="polar", f=lambda th, a: a + np.cos(5 * th), domain=(0, TAU), a=(0.0, 1.2), a_name="a",
         label=["r = a + cos(5θ)"],
         title="10 Petals Become 1 Flower", hook="ADD A NUMBER, CHANGE THE FLOWER",
         question="At which moment does it change most?", desc="Rose curve with a growing constant offset a"),
    dict(id="superellipse", kind="param", domain=(0, TAU), a=(0.66, 4.0), a_name="n", pingpong=True,
         f=lambda t, n: (_sgnpow(np.cos(t), 2 / n), _sgnpow(np.sin(t), 2 / n)),
         label=["|x|ⁿ + |y|ⁿ = 1"],
         title="From Star to Square with 1 Exponent", hook="STAR, CIRCLE, SQUARE: SAME EQUATION",
         question="Which shape do you like most?", desc="Lamé superellipse with a changing exponent n"),
    # --- 21-30 ---
    dict(id="bessel", kind="cartesian", f=_bessel, domain=(0, 30), a=(0.0, 5.0), a_name="ν", view=(0, 30, -0.5, 1.05),
         label=["y = J_ν(x)", "Bessel function of order ν"],
         title="The Bessel Function Behind Every Drum", hook="THE SHAPE OF A VIBRATING DRUM",
         question="Which order looks most like a drum ripple?", desc="Bessel function of the first kind with a changing order ν"),
    dict(id="conics", kind="polar", f=lambda th, e: 1 / (1 + e * np.cos(th)), domain=(0, TAU), a=(0.0, 0.8), a_name="e",
         pingpong=True,
         label=["r = 1 / (1 + e·cos θ)"],
         title="Every Planet Orbit in 1 Equation", hook="EVERY ORBIT IS THIS EQUATION",
         question="Which orbit would you choose for Earth?", desc="Conic section in polar form with a changing eccentricity e"),
    dict(id="trefoil", kind="param", domain=(0, TAU), a=(2.0, 0.5), a_name="a", pingpong=True,
         f=lambda t, a: (np.sin(t) + a * np.sin(2 * t), np.cos(t) - a * np.cos(2 * t)),
         label=["x = sin t + a·sin 2t", "y = cos t − a·cos 2t"],
         title="A 3-Loop Knot from 2 Sines", hook="A KNOT WITH THREE LOOPS",
         question="Where would you cut it to untie it?", desc="Trefoil knot projection with a changing loop size a"),
    dict(id="takagi", kind="cartesian", f=_takagi, domain=(0, 1), a=(0, 10), a_int=True, a_name="N", samples=8192,
         view=(-0.02, 1.02, -0.05, 0.75),
         label=["y = Σ s(2ⁿ·x) / 2ⁿ", "s = distance to nearest integer,  n = 0 … N"],
         title="10 Triangles Build a Fractal Mountain", hook="TRIANGLES BUILD A MOUNTAIN",
         question="Does it remind you of a mountain range?", desc="Takagi (blancmange) curve from sums of triangle waves"),
    dict(id="cassini", kind="polar", f=_cassini, domain=(0, TAU), a=(1.0, 1.6), a_name="b", samples=6000,
         label=["(x² + y²)² − 2(x² − y²) = b⁴ − 1"],
         title="Infinity Sign to Oval in 1 Parameter", hook="FROM INFINITY TO AN OVAL",
         question="Did you catch the moment it splits?", desc="Cassini ovals starting from the lemniscate"),
    dict(id="epicycle-star", kind="param", domain=(0, TAU), a=(0.3, 1.0), a_name="a", pingpong=True,
         f=lambda t, a: _z(np.exp(1j * t) + a * np.exp(-4j * t)),
         label=["z = exp(it) + a·exp(−4it)"],
         title="2 Circles Make a 5-Point Star", hook="TWO CIRCLES MAKE A STAR",
         question="When does the circle become a star?", desc="Sum of two counter-rotating circles"),
    dict(id="dirichlet", kind="cartesian", f=_dirichlet, domain=(-np.pi, np.pi), a=(1, 20), a_int=True, a_name="N",
         view=(-np.pi, np.pi, -0.3, 1.05), samples=4000,
         label=["y = sin((N + ½)x) / ((2N+1)·sin(x/2))"],
         title="20 Waves Focus into 1 Spike", hook="WAVES THAT FOCUS INTO A SPIKE",
         question="What happens when N goes to infinity?", desc="Normalized Dirichlet kernel with a growing N"),
    dict(id="wobbly-spiral", kind="polar", f=lambda th, a: th + a * np.sin(8 * th), domain=(0, 4 * TAU), a=(0.0, 3.0),
         a_name="a", pingpong=True, samples=5000,
         label=["r = θ + a·sin(8θ)"],
         title="A Spiral That Learns to Dance in 8 Beats", hook="A SPIRAL THAT STARTS TO DANCE",
         question="Calm spiral or dancing spiral?", desc="Archimedean spiral with an added wobble"),
    dict(id="trochoid", kind="param", domain=(0, 3 * TAU), a=(0.5, 2.0), a_name="a", pingpong=True,
         f=lambda t, a: (t - a * np.sin(t), 1 - a * np.cos(t)),
         label=["x = t − a·sin t", "y = 1 − a·cos t"],
         title="A Rolling Wheel Draws 3 Loops", hook="WHAT A ROLLING WHEEL DRAWS",
         question="Where on the wheel is the pen?", desc="Trochoid: a point on a rolling wheel"),
    dict(id="x-sin-inv", kind="cartesian", f=lambda x, a: x * np.sin(a / np.where(x == 0, 1e-9, x)), domain=(-1, 1),
         a=(1.0, 5.0), a_name="a", pingpong=True, view=(-1, 1, -1.05, 1.05), samples=12000,
         label=["y = x·sin(a / x)"],
         title="Infinite Wiggles in 1 Tiny Interval", hook="INFINITE WIGGLES NEAR ZERO",
         question="How many wiggles fit near zero?", desc="x·sin(a/x): infinitely many oscillations squeezed toward zero"),
]

assert len(EXPRESSIONS) == 30 and len({e["id"] for e in EXPRESSIONS}) == 30

BY_ID = {e["id"]: e for e in EXPRESSIONS}
