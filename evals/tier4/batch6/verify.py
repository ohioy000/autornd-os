"""The advisor's verification of tier-4 batch 6 (2026-10-18; generator x-ai/grok-4.7
on generator v4.1, two calls; the owner's "2 first": a larger batch of traps the
corpus does not state). Every option, with the correct method and with the trap
missed, recomputed from the request and the corpus pages, not from the generator's
option tables."""
from math import pi, sqrt, log, acos, sin, exp

def t451(trap=False):
    ri, Ti, Ta, h = 0.060, 200.0, 25.0, 8.0
    rows = {'KJ-20': (14, 20, .040, .0030, 1.1), 'KJ-40': (26, 40, .036, .0035, 2.0), 'KJ-55': (39, 55, .032, .0015, 2.6), 'KJ-70': (52, 70, .034, .0020, 3.4)}
    out = {}
    for m, (cost, t, k20, b, kg) in rows.items():
        ro = ri + t / 1000; Ts = 40.0
        for _ in range(200):
            k = k20 if trap else k20 * (1 + b * ((Ti + Ts) / 2 - 20))
            q = 2 * pi * (Ti - Ta) / (log(ro / ri) / k + 1 / (h * ro)); Ts = Ta + q / (2 * pi * ro * h)
        out[m] = (cost, q <= 80 and Ts <= 50 and t <= 60 and kg <= 3.0, round(q, 2), round(Ts, 2))
    return out

def t452(trap=False):
    # triangular profile: theta = a*(T/2)**2, so a = 4*theta/T**2 (the generator wrote 2*theta/T**2 but used 39.27)
    a_t = 4 * (pi / 2) / 0.40**2; w_t = 2 * (pi / 2) / 0.40
    rows = {'A20': (610, 10, .00018, 2.5, 4.8, 3000, 80), 'A40': (470, 20, .00015, 1.5, 2.4, 3000, 80), 'A60': (690, 30, .00025, 1.8, 3.5, 4000, 90), 'A80': (880, 40, .00040, 2.2, 5.0, 5000, 120)}
    out = {}
    for m, (cost, N, Jm, Tc, Tp, nmax, Tout) in rows.items():
        J = Jm + (0 if trap else 1.20 / N**2); am = N * a_t
        Tacc = J * am + 4.0 / N; Tdec = J * am - 4.0 / N; Trms = sqrt((Tacc**2 + Tdec**2) * 0.20 / 2.0)
        out[m] = (cost, Tacc <= Tp and Trms <= Tc and N * w_t <= nmax * 2 * pi / 60 and Tacc * N <= Tout, round(Tacc, 3))
    return out

def t453(trap=False):
    rho20, al, d, c = 1.724e-8, 0.00393, 8890, 385
    phi = acos(0.85)
    rows = {'V50': (9.2, 50, 196, .4397), 'V70': (13.4, 70, 246, .3140), 'V95': (18.6, 95, 301, .2314), 'V120': (24.0, 120, 352, .1832)}
    out = {}
    for m, (cost, S, amp, R) in rows.items():
        dV = sqrt(3) * 180 * (R * .85 + .080 * sin(phi)) * .040
        A = S * 1e-6; x = 12000**2 * 0.8 * rho20 * al / (A**2 * d * c)
        Tf = 20 + ((1 + al * 70) * exp(x) - 1) / al
        ok_fault = True if trap else Tf <= 250
        out[m] = (cost, amp >= 180 and dV <= 12 and ok_fault, round(Tf, 1), round(dV, 2))
    return out

def t453_iec_kfactor():
    """IEC 60364-4-43 k-factor check: copper, 90 to 250 degC, k = 143. Minimum section."""
    return round(12000 * sqrt(0.8) / 143, 1)

def t454(trap=False):
    """T4-54 (dropped): with 20 kPa gauge taken as absolute, no pump passes."""
    g, rho = 9.81, 992
    p = (20 if trap else 101.3 + 20) * 1000
    npsha = (p - 7380) / (rho * g) + 1.5 - 1.2
    rows = {'Lark-210': (1850, 26, .68, 3.80), 'Lark-340': (2480, 34, .75, 4.50), 'Lark-090': (3250, 22, .60, .85), 'Lark-420': (4100, 42, .80, 5.50)}
    return {m: (cost, H >= 28 and rho * g * .040 * H / eta <= 19000 and npsha >= 1.3 * r, round(npsha, 3)) for m, (cost, H, eta, r) in rows.items()}

def t455(trap=False):
    T = 15 if trap else 15 * (240 / 80) / 0.96
    rows = {'K-20': (640, 1200, 22, 5.5, 18), 'K-40': (910, 1200, 40, 9.6, 28), 'K-55': (1280, 1200, 55, 13.2, 36), 'K-75': (1710, 1200, 75, 18.1, 48)}
    return {m: (p, Tr >= T and n >= 1100 and I <= 16 and kg <= 40, round(Tr / T, 3)) for m, (p, n, Tr, I, kg) in rows.items()}

def t456(trap=False):
    rows = {'PF-60x10': (60, 10), 'PF-70x10': (70, 10), 'PF-80x10': (80, 10), 'PF-80x12': (80, 12)}
    out = {}
    for m, (w, t) in rows.items():
        kg = w * t * 1e-6 * 1.5 * 7850; s = 90000 / ((w if trap else w - 18) * t)
        out[m] = (round(kg, 3), s <= 155 and w >= 40 and t >= 6 and kg <= 20, round(s, 2))
    return out

def t457(trap=False):
    rho, pv = (860, 2000) if trap else (820, 45000)
    npsha = (101300 - pv) / (rho * 9.81) + 2.5 - 1.2
    rows = {'H-210': (2400, 20, 26, 10.0, 4.0, 120), 'H-240': (3100, 21, 28, 8.5, 5.5, 120), 'H-280': (4550, 24, 30, 6.4, 7.5, 120), 'H-320': (5900, 30, 32, 5.5, 9.0, 120)}
    return {m: (p, Q >= 18 and H >= 22 and npsha >= 1.15 * r and P <= 15 and Tl >= 80, round(npsha, 3)) for m, (p, Q, H, r, P, Tl) in rows.items()}

def t458(trap=False, exact=False):
    rows = {'B-160': (2000, 230.9, 160, .080), 'B-200': (2800, 288.7, 200, .075), 'B-320': (4500, 461.9, 320, .055), 'B-500': (6100, 721.7, 500, .040)}
    I = 75000 / (sqrt(3) * 400); out = {}
    for m, (p, Ir, S, x) in rows.items():
        ix = (75 / S if trap else 75 / 100) * x
        drop = 100 * (sqrt((1 + ix * .6)**2 + (ix * .8)**2) - 1) if exact else 100 * ix * .6
        out[m] = (p, drop <= 3.0 and Ir >= I, round(drop, 3))
    return out

def best(t):
    ok = {k: v for k, v in t.items() if v[1]}
    return min(ok, key=lambda k: ok[k][0]) if ok else None

if __name__ == '__main__':
    for name, fn in (('T4-51', t451), ('T4-52', t452), ('T4-53', t453), ('T4-54 (dropped)', t454), ('T4-55', t455), ('T4-56', t456), ('T4-57', t457), ('T4-58', t458)):
        print(name, 'correct:', best(fn()), '| trap missed:', best(fn(True)))
        print('   correct:', fn()); print('   trapped:', fn(True))
    print('T4-53 IEC k-factor minimum section (mm2):', t453_iec_kfactor())
    print('T4-58 exact drop: correct', best(t458(exact=True)), t458(exact=True), '| trapped', best(t458(True, True)))
