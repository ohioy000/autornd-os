"""The advisor's independent verification of tier-4 batch 2 (2026-10-17).

Each kept candidate is recomputed from its request and corpus pages with the
standard method, its design space is searched, and the result is checked
against the alternative methods an expert might use. Run from the repository
root: python3 -I evals/tier4/batch2/verify.py"""
import math

# ---- T4-15: Voss-Metra VM-C strut, EN 1993-1-1/-1-3 with the maker's rules
E, G, FY, L, NED = 210000, 81000, 355, 3000, 115
SECS = {'VM-C140': (620, 1.950e6, .580e6, 640, 2.40e9, 42.0), 'VM-C160': (800, 3.200e6, .923e6, 1067, 5.30e9, 49.0),
        'VM-C180': (1080, 5.450e6, 1.620e6, 2590, 13.50e9, 55.4), 'VM-C200': (1350, 8.200e6, 2.404e6, 4500, 28.50e9, 62.0)}
def t415(name, torsional_flexural=True, k_vm=0.92):
    A, Ix, Iy, J, Iw, x0 = SECS[name]
    rx, ry = math.sqrt(Ix / A), math.sqrt(Iy / A); r0 = math.sqrt(rx**2 + ry**2 + x0**2)
    Ncx = math.pi**2 * E * Ix / L**2 / 1e3; Ncy = math.pi**2 * E * Iy / L**2 / 1e3
    NcT = (G * J + math.pi**2 * E * Iw / L**2) / r0**2 / 1e3; beta = 1 - (x0 / r0)**2
    NTF = (Ncx + NcT) / (2 * beta) * (1 - math.sqrt(1 - 4 * beta * Ncx * NcT / (Ncx + NcT)**2))
    Ncr = min(Ncy, NTF) if torsional_flexural else Ncy
    lam = math.sqrt(A * FY / 1e3 / Ncr); Phi = .5 * (1 + .34 * (lam - .2) + lam**2); chi = 1 / (Phi + math.sqrt(Phi**2 - lam**2))
    Nb = k_vm * chi * A * FY / 1e3
    return dict(A=A, r_y=ry, r_0=r0, N_cr_y=Ncy, N_cr_T=NcT, N_cr_TF=NTF, lambda_bar=lam, chi=chi, N_b_Rd=Nb, Utilization=NED / Nb), (lam <= 1.30 and Nb >= NED)

# ---- T4-16: Kaelen-Vortec KV-Chem pump selection with the maker's rules
RHO, NU, PV, PATM, GR, QH, Q, DP, EPS = 1150, 1.2e-6, 18.0, 101.3, 9.81, 90.0, .025, .1023, .045e-3
PUMPS = {'KV-100-200': (208, 46.5, .00095, 92.0, .770, .00011, 1.35, 15.0), 'KV-80-250': (250, 64.0, .00120, 85.0, .745, .00015, 1.48, 18.5),
         'KV-100-250': (250, 62.0, .00100, 100.0, .780, .00010, 1.25, 22.0), 'KV-125-250': (250, 65.0, .00080, 130.0, .790, .00008, 1.15, 30.0)}
def friction(Re, method):
    rel = EPS / DP
    if method == 'colebrook':
        f = .02
        for _ in range(80): f = (-2 * math.log10(rel / 3.7 + 2.51 / (Re * math.sqrt(f))))**-2
        return f
    if method == 'swamee-jain': return .25 / math.log10(rel / 3.7 + 5.74 / Re**.9)**2
    if method == 'haaland': return (-1.8 * math.log10((rel / 3.7)**1.11 + 6.9 / Re))**-2
def t416_system(method='colebrook'):
    v = 4 * Q / (math.pi * DP**2); Re = v * DP / NU; f = friction(Re, method); vh = v**2 / (2 * GR)
    Hsys = 22.0 + (185.0 - 101.3) * 1000 / (RHO * GR) + (f * 85 / DP + 14.0) * vh
    NPa = (PATM - PV) * 1000 / (RHO * GR) - 3.20 - (f * 6.0 / DP + 2.8) * vh
    return v, f, Hsys, NPa
def t416(model, method='colebrook', trim_penalty=True, derate=True, por=True):
    v, f, Hsys, NPa = t416_system(method)
    D0, H0, S0, QB0, emax, ke, NR0, Pm = PUMPS[model]
    Dt = next((d for d in range(math.ceil(.85 * D0), D0 + 1) if H0 * (d / D0)**2 - S0 * QH**2 >= Hsys), None)
    if Dt is None: return None, False
    Hp = H0 * (Dt / D0)**2 - S0 * QH**2; QB = QB0 * Dt / D0
    NRc = NR0 * (D0 / Dt)**1.5 if trim_penalty else NR0
    eta = emax - ke * (QH - QB)**2 - .25 * (1 - Dt / D0); P = RHO * GR * Q * Hp / (1000 * eta); Pd = (.88 if derate else 1.0) * Pm
    ok = (not por or .70 * QB <= QH <= 1.15 * QB) and NPa >= 1.15 * NRc + .50 and P <= Pd
    return dict(Model=model, D_trim=Dt, v_pipe=v, f_Darcy=f, H_sys=Hsys, NPSH_A=NPa, NPSH_R_corr=NRc, H_pump=Hp, eta_pump=eta, P_shaft=P, P_motor_derated=Pd), ok

if __name__ == '__main__':
    print("===== T4-15")
    for n in SECS:
        c, ok = t415(n); _, trap = t415(n, torsional_flexural=False)
        print(f"  {n}: {'PASS' if ok else 'fail'} (lambda {c['lambda_bar']:.3f}, N_b,Rd {c['N_b_Rd']:.1f} kN); with the trap (torsional-flexural mode missed): {'PASS' if trap else 'fail'}")
    print("  answer: the lightest passing section is", min((SECS[n][0], n) for n in SECS if t415(n)[1])[1])
    print("===== T4-16")
    for m in ('colebrook', 'swamee-jain', 'haaland'):
        valid = {p: r for p in PUMPS for r, ok in [t416(p, m)] if ok}
        best = min(valid, key=lambda p: valid[p]['P_shaft'])
        print(f"  {m}: f {t416_system(m)[1]:.4f}, H_sys {t416_system(m)[2]:.2f} m; valid {sorted(valid)}; answer {best} at D_trim {valid[best]['D_trim']} mm, P {valid[best]['P_shaft']:.2f} kW")
    trapped = {p for p in PUMPS if t416(p, trim_penalty=False, derate=False, por=False)[1]}
    print("  with the trap (no trim-NPSH penalty, no derating, no POR check), these also pass:", sorted(trapped))
