"""The advisor's verification of tier-4 batch 5 (2026-10-18; generator x-ai/grok-4.7
on generator v4, the owner's "1 first": traps the corpus does not state). Every
option, with the correct method and with the trap missed, recomputed from the
request and the corpus page, not from the generator's option table."""
from math import pi, sqrt

def t441(trap=False):
    a = 0.0 if trap else 0.25 / 0.25
    F = 800 * (9.81 + a); T = F * 0.20; n = 0.25 / (2 * pi * 0.20) * 60; P = F * 0.25
    rows = {'WR-180': (19, 1480, 32, 8000, 2800), 'WR-220': (24, 1620, 30, 9500, 3500), 'WR-260': (33, 1900, 28, 12000, 4000), 'WR-310': (45, 2500, 24, 15000, 5000)}
    return {m: (kg, Tm >= T and nm >= n and Fr >= F and Pm >= P, round(Tm / T, 3)) for m, (kg, Tm, nm, Fr, Pm) in rows.items()}

def t442(trap=False):
    I = 15000 / 0.90 / 0.84 / (sqrt(3) * 400); Ic = I if trap else sqrt(2) * I
    rows = {'VL-25': (410, 33, 18), 'VL-36': (520, 38, 18.5), 'VL-42': (640, 46, 22), 'VL-60': (890, 62, 30)}
    return {m: (p, In >= Ic and 380 <= 400 <= 480 and Pn >= 15, round(In / Ic, 3)) for m, (p, In, Pn) in rows.items()}

def t443(trap=False):
    H = 420000 / ((998 if trap else 760) * 9.81)
    rows = {'CP-20': (980, 20, 46, .78, 3.0, 12), 'CP-40': (1720, 22, 62, .75, 4.2, 15), 'CP-50': (1490, 25, 70, .70, 6.4, 18), 'CP-80': (2100, 28, 75, .66, 3.8, 22)}
    out = {}
    for m, (p, Q, Hm, eta, npshr, Pmot) in rows.items():
        Ps = 0.018 * 420000 / eta / 1000
        out[m] = (p, Q >= 18 and Hm >= H and Pmot >= Ps and npshr <= 5.5, round(Hm / H, 3))
    return out

def t444_methods():
    """T4-44 (dropped): PS-3's buckling factor of safety under three standard methods."""
    A, I, E, fy, L, N = 0.0032, 2.8e-6, 210e9, 250e6, 4.0, 120e3
    r = sqrt(I / A); lam = L / r
    euler = pi**2 * E * I / L**2 / N
    Fe = pi**2 * E / lam**2
    aisc = (0.658 ** (fy / Fe) * fy if fy / Fe <= 2.25 else 0.877 * Fe) * A / N
    lb = sqrt(fy * A / (pi**2 * E * I / L**2))
    def ec3(alpha):
        phi = 0.5 * (1 + alpha * (lb - 0.2) + lb**2); chi = min(1.0, 1 / (phi + sqrt(phi**2 - lb**2)))
        return chi * fy * A / N
    return {'L/r': round(lam, 1), 'Euler': round(euler, 3), 'AISC E3': round(aisc, 3), 'EC3 curve a': round(ec3(.21), 3), 'EC3 curve b': round(ec3(.34), 3), 'EC3 curve c': round(ec3(.49), 3)}

def best(t, key=lambda v: v[0]):
    ok = {k: v for k, v in t.items() if v[1]}
    return min(ok, key=lambda k: key(ok[k])) if ok else None

if __name__ == '__main__':
    for name, fn in (('T4-41', t441), ('T4-42', t442), ('T4-43', t443)):
        print(name, 'correct:', best(fn()), '| trap missed:', best(fn(True)))
        print('   correct:', fn()); print('   trapped:', fn(True))
    print('T4-44 (dropped): PS-3 buckling factor of safety (needs 2.5) by method:', t444_methods())
