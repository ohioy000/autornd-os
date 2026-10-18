"""The advisor's verification of tier-4 batch 3 (2026-10-18): every catalogue option
under the correct method and with the trap missed, from the corpus rules."""
import math

def t421(trap=False):
    a = (150 * 2 * math.pi / 60) / 0.20; T1, T2, T3 = 45 + .45 * a, 85.0, abs(45 - .45 * a)
    rms = math.sqrt((T1**2 * .2 + T2**2 * .4 + T3**2 * .2) / (1.0 if trap else 0.8))
    frames = {75: (38, 25, 9800, 2500), 90: (45, 30, 14200, 3600), 115: (55, 35, 21000, 5200)}
    out = {}
    for m, fr, i, TN, Tmax, n1max, Jg, eta, mass in [('KGD-75-08', 75, 8, 75, 200, 5000, .0068, .96, 4.2), ('KGD-90-08', 90, 8, 92, 300, 4500, .0085, .96, 6.8),
                                                     ('KGD-90-10', 90, 10, 105, 330, 4500, .00798, .96, 7.0), ('KGD-115-05', 115, 5, 140, 450, 4000, .0052, .97, 11.2),
                                                     ('KGD-115-08', 115, 8, 175, 520, 4000, .0091, .96, 11.5)]:
        A, Lr, Cr, Frmax = frames[fr]; Feq = 2400 * (A + 45) / (A + Lr)
        L10 = 1e6 / (60 * 90.0) * (Cr / (Feq * 1.15))**(10 / 3); Tth = TN * .82 * .90
        Tm = max(T1 / (i * eta) + (.0006 + Jg) * i * a, T2 / (i * eta))
        ok = (max(T1, T2, T3) <= Tmax / 1.15 and rms <= Tth and Feq <= Frmax and L10 >= 15000 and Tm <= 18.0 and 150 * i <= n1max)
        out[m] = (mass, ok, dict(rms=round(rms, 2), Tth=round(Tth, 2), Feq=round(Feq), L10=round(L10), Tm=round(Tm, 2)))
    return out

def t422(trap=None, travel='mandatory'):
    Gf, Pv, Pc = .79, 32.0, 8096.0; FF = .96 - .28 * math.sqrt(Pv / Pc)
    def h(R):
        if travel == 'mandatory':
            return 512 * R if R <= .05 else (100 * R if R > .5 else 25 + 78.947 * (R - .05))
        return 500 * R if R <= .05 else 25 + 78.947 * (R - .05)
    out = {}
    for m, d, trim, Cv100, FL, Fkc, Fp, mass in [('VFC-9080-S', 80, 'S', 90, .82, .518, .945, 48), ('VFC-9080-M', 80, 'M', 62, .94, .670, .975, 54),
                                                 ('VFC-9100-S', 100, 'S', 140, .82, .518, .967, 72), ('VFC-9100-M', 100, 'M', 80, .94, .730, .964, 79),
                                                 ('VFC-9150-M', 150, 'M', 125, .94, .720, 1.0, 135)]:
        dP = 850.0; Cv0 = 145 / (.865 * math.sqrt((dP / 100) / Gf))
        Km = 1.0 if (trim == 'S' or dP / 1600 <= .5 or trap == 'no_Km') else (.945 if d == 80 else .873)
        hmax = h(Cv0 / (Fp * Km) / Cv100)
        Cv0min = 5 / (.865 * math.sqrt((700 / 100) / Gf)); hmin = h(Cv0min / Fp / Cv100)
        dPic = (FL**2 if trap == 'FL' else Fkc) * Fp**2 * (1600 - FF * Pv)
        ok = dP <= dPic and hmax <= 85 and hmin >= 10
        out[m] = (mass, ok, dict(hmax=round(hmax, 1), hmin=round(hmin, 1), dPic=round(dPic, 1)))
    return out

def t423(trap=None):
    rho, cp, mu, Q = 1055, 3450, .0021, 6.0 / 60000; nu = mu / rho
    Tout = 45 + 1300 / (rho * Q * cp); Rtim = .12 / 36
    out = {}
    for m, alloy, N, Ach, Wf, Rcat, Kh, Kp, mass in [('TVC-180-AL', 'AL', 14, 3, 90, .05, 1.24, .115, 1.15), ('TVC-200-AL', 'AL', 18, 3, 90, .0485, .98, .098, 1.45),
                                                     ('TVC-250-AL', 'AL', 16, 4, 75, .0451, 1.07, .1, 1.85), ('TVC-220-CU', 'CU', 16, 3, 75, .0395, 1.2, .11, 2.6),
                                                     ('TVC-260-CU', 'CU', 20, 3, 75, .038, .94, .095, 3.1)]:
        v = Q / (N * Ach * 1e-6); vmax = 2.2 if alloy == 'AL' else 3.5
        dP = Kh * (rho / 997) * (nu / .89e-6)**.25 * 6**1.75 + Kp * (rho / 1000) * 36
        Rconv = Rcat * (1 if trap == 'no_factors' else (Wf / 60)**.35 * 1.28)
        Tb = (45 if trap == 'inlet' else Tout) + 650 * (Rtim + Rconv)
        out[m] = (mass, v <= vmax and dP <= 38 and Tb <= 95, dict(v=round(v, 3), dP=round(dP, 2), Tb=round(Tb, 2)))
    return out

def t424(trap=None):
    Calt = 1.0 if trap == 'no_CaltV' else 1 - .015 * 9; Malt = 1.0 if trap == 'no_Malt' else 1.62
    Ieff = math.sqrt((90 / (5 / 7))**2 + (140 / (5 / 6))**2)
    out = {}
    for m, V, C, ESR, Rth, cost in [('EPC-1100-80', 1100, 80, 1.55e-3, 4.0, 140), ('EPC-1200-60', 1200, 60, 1.8e-3, 5.685, 130), ('EPC-1250-80', 1250, 80, 1.35e-3, 4.38, 185)]:
        for N in range(1, 9):
            Tc = 65 + (Ieff / N)**2 * ESR * Rth * Malt; Ct = N * C * 1e-6
            dV = math.sqrt(3) * 140 / (4 * 40e3 * Ct) + 2 * math.sqrt(3) * 140 * (ESR / (5 / 6)**2) / N
            ok = N * C >= 220 and 1035 <= V * Calt and Tc <= 105 and dV <= 12
            out[f"{N} x {m}"] = (N * cost, ok, dict(Tc=round(Tc, 2), Vlim=round(V * Calt, 1), dV=round(dV, 2)))
    return out

def best(table):
    ok = {k: v for k, v in table.items() if v[1]}
    return min(ok, key=lambda k: ok[k][0]) if ok else None

if __name__ == '__main__':
    print("T4-21 correct:", best(t421()), "| trap (RMS over full cycle):", best(t421(trap=True)))
    for k, v in t421().items(): print("   ", k, v)
    for tr in ('mandatory', 'two-slope'):
        print(f"T4-22 [{tr}] correct:", best(t422(travel=tr)), "| trap F_L:", best(t422('FL', tr)), "| trap no K_m:", best(t422('no_Km', tr)))
    for k, v in t422().items(): print("   ", k, v)
    print("T4-23 correct:", best(t423()), "| trap no factors:", best(t423('no_factors')), "| trap inlet temp:", best(t423('inlet')))
    for k, v in t423().items(): print("   ", k, v)
    print("T4-24 correct:", best(t424()), "| trap no M_alt:", best(t424('no_Malt')), "| trap no C_alt,V:", best(t424('no_CaltV')))
    for k in ('4 x EPC-1200-60', '5 x EPC-1200-60', '3 x EPC-1100-80', '4 x EPC-1250-80'): print("   ", k, t424()[k])
