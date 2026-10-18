"""The advisor's verification of tier-4 batch 4 (2026-10-18; generator x-ai/grok-4.7,
the owner's "1 then 2": a non-Gemini generator). Every option, under the corpus
rules and with the trap missed."""

def t431(trap=False):
    Treq = 1.5 * (25 if trap else 55); f = 1 - 0.0015 * (4200 - 3000)
    rows = {'ND-C20': (85, 40, 6000, 1.5, .35), 'ND-C35': (120, 70, 5500, 1.2, .55), 'ND-C50': (165, 110, 4800, 1.0, .80), 'ND-C80': (210, 180, 4000, 1.5, 1.10)}
    return {m: (p, Tc * f >= Treq and n >= 4200 and a >= .9 and ms <= 1.0, round(Tc * f, 2)) for m, (p, Tc, n, a, ms) in rows.items()}

def t432(trap=False):
    k = (1 - .015 * 10) * (1.0 if trap else .85)
    rows = {'HC-25': (42, 25, 40), 'HC-40': (58, 40, 60), 'HC-50': (76, 50, 80), 'HC-65': (99, 65, 100)}
    return {m: (p, I * k >= 32 and Ith * k >= 40, round(I * k, 3)) for m, (p, I, Ith) in rows.items()}

def t433(trap=False):
    cq, ch, ce, cn = (1, 1, 1, 1) if trap else (.82, .90, .70, 1.15)
    rows = {'PP-1': (980, .0065, 32, 3.0, 2.2), 'PP-2': (1280, .0078, 36, 4.0, 2.6), 'PP-3': (1540, .0095, 40, 5.5, 3.0), 'PP-4': (1890, .0120, 45, 7.5, 3.4)}
    out = {}
    for m, (p, Q, H, P, N) in rows.items():
        Ps = P * .9 / ce if not trap else P
        out[m] = (p, cq * Q >= .006 and ch * H >= 30 and Ps <= 6.0 and 4.5 >= cn * N + .5, round(cq * Q, 6))
    return out

def t434(trap=False):
    Rreq = (86 - 30) / 100; o = 1.0 if trap else 1.25
    rows = {'VX-180': (18, .70, 100, .40), 'VX-250': (27, .50, 110, .62), 'VX-320': (36, .38, 115, .88), 'VX-400': (48, .28, 118, 1.15)}
    return {m: (p, o * R + .05 <= Rreq and L <= 120 and ms <= 1.0, round(o * R + .05, 3)) for m, (p, R, L, ms) in rows.items()}

def best(t):
    ok = {k: v for k, v in t.items() if v[1]}
    return min(ok, key=lambda k: ok[k][0]) if ok else None

if __name__ == '__main__':
    for name, fn in (('T4-31', t431), ('T4-32', t432), ('T4-33', t433), ('T4-34', t434)):
        print(name, 'correct:', best(fn()), '| trap missed:', best(fn(True)))
