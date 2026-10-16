"""The advisor's independent verification of the tier-4 pilot batch (2026-10-16).

For each candidate it:
- recomputes every requirement from the request's own formulas, or for F2 from
  the corpus pages, never from the candidate's own `check` strings, some of
  which pin the reference choice;
- checks the reference design and each known-wrong design;
- searches the whole design space for every feasible design.

Run from the repository root: python3 -I evals/tier4/pilot/verify.py"""
import json, math, itertools, sys
items = {o['id']: o for o in json.load(open('evals/tier4/pilot/candidates.json'))}

def t401(motor, R, z1, z2):
    M = {'M1': (6500, 100.0, 130, .018, 620), 'M2': (7500, 150.0, 105, .014, 680),
         'M3': (7500, 100.0, 155, .024, 790), 'M4': (9000, 150.0, 125, .020, 860)}[motor]
    Prat, w, Tmax, Jm, cm = M
    a = 2 * (z1 + z2); i = z2 / z1
    v = w * R / i
    Ps = 1450 * 9.81 * v / (0.96 * 0.97)
    Ts = Ps / w; Jd = 450 * R**4
    Jt = Jm + (Jd + 1450 * R**2) / (i**2 * 0.96 * 0.97)
    Tpk = Ts + Jt * w / 4.20
    Tpin = 0.97 * Tpk; d1 = 4 * z1
    Kv = 1 + 0.05 * (w * d1 / 2000); Y = 2.45 + 3.2 / z1
    sb = 2000 * Tpin / (4 * 45 * d1) * Kv * Y
    sc = 1040 * math.sqrt(2000 * Tpin * Kv * (i + 1) / (45 * d1**2 * i))
    cost = cm + 1.8 * (z1 + z2) + 2500 * R
    vals = dict(a=a, v_act=v, P_steady=Ps, T_peak=Tpk, sigma_b=sb, sigma_c=sc, Cost=cost)
    req = dict(R1=a <= 235, R2=abs(v - .42) <= .0084, R3=Ps <= .9 * Prat, R4=Tpk <= .85 * Tmax,
               R5=sb <= 43.0 and sc <= 1050, R6=cost <= 1250)
    return vals, req
def space401():
    for m, R, z1, z2 in itertools.product(['M1','M2','M3','M4'], [.12,.14,.16,.18,.20], range(17,22), range(60,121)):
        yield dict(Motor_ID=m, R=R, z1=z1, z2=z2), t401(m, R, z1, z2)

def t402(Q, Lid, f, Nc):
    q = {'Q1': (4.2e-3, 38e-9, 14e-9, 11.0, 3.80), 'Q2': (3.0e-3, 54e-9, 18e-9, 9.5, 4.90), 'Q3': (2.2e-3, 78e-9, 24e-9, 8.5, 6.40)}[Q]
    l = {'L1': (4.7e-6, 2.8e-3, 34.0, .012, 4.20), 'L2': (6.8e-6, 3.6e-3, 31.0, .015, 4.80),
         'L3': (10e-6, 4.9e-3, 29.0, .018, 5.60), 'L4': (15e-6, 6.8e-3, 28.0, .022, 6.50)}[Lid]
    Rds, Qg, tsw, Rth, cq = q; L, Rdc, Isat, kc, cl = l
    fs = f * 1e3
    dI = 12.0 * (1 - .25) / (L * fs); Ipk = 25 + dI / 2
    dV = 1000 * dI * math.sqrt((0.012 / Nc)**2 + (1 / (8 * fs * Nc * 47e-6))**2)
    I2 = 25**2 + dI**2 / 12
    Pm = I2 * Rds + 0.5 * 48 * 25 * tsw * fs + 2 * Qg * 10 * fs
    Tj = 58 + Pm * Rth
    Pi = I2 * Rdc + kc * (fs / 100e3)**1.5 * dI**2
    eta = 100 * 300 / (300 + Pm + Pi)
    cost = cq + cl + .65 * Nc
    vals = dict(dI_L=dI, I_pk=Ipk, dV_out=dV, P_mos=Pm, P_ind=Pi, T_j=Tj, eta=eta, Cost=cost)
    req = dict(R1=True, R2=dI <= 7.5 and Ipk <= .9 * Isat, R3=dV <= 30.0, R4=Tj <= 105.0, R5=eta >= 97.0, R6=cost <= 12.50)
    return vals, req
def space402():
    for Q, L, f, N in itertools.product(['Q1','Q2','Q3'], ['L1','L2','L3','L4'], [150,200,250,300], [2,3,4,5,6]):
        yield dict(MOSFET_ID=Q, Inductor_ID=L, f_sw=f, N_c=N), t402(Q, L, f, N)

def t403(P, D):
    p = {'P1': (260, 650000, .74, 1.25, 12000, 1450), 'P2': (285, 720000, .78, 1.45, 14000, 1680), 'P3': (330, 800000, .76, 2.25, 16000, 1890)}[P]
    a, b, eta, c, d, cost_p = p; rho, mu, Q = 1045, .0032, .0120
    v = 4 * Q / (math.pi * D**2); Re = rho * v * D / mu; f = .3164 * Re**-.25 + .0035
    q = rho * v**2 / 2000
    dPsys = (f * 90.0 / D + 14.5) * q; dPp = a - b * Q**2; dPv = dPp - dPsys
    dPs = (f * 6.0 / D + 2.2) * q
    NPa = 1000 * (95.0 - 18.0 - dPs) / (rho * 9.81) - 2.40; NPr = c + d * Q**2
    Psh = 1000 * Q * dPp / eta; cost = cost_p + (380 * D**2 + 12.0) * 90.0
    vals = dict(v=v, Re=Re, f=f, dP_sys=dPsys, dP_valve=dPv, NPSH_a=NPa, NPSH_r=NPr, P_shaft=Psh, Cost=cost)
    req = dict(R1=v <= 3.00, R2=8.0 <= dPv <= 35.0, R3=NPa >= 1.03 * NPr, R4=Psh <= 2900.0, R5=cost <= 3000.0)
    return vals, req
def space403():
    for P, D in itertools.product(['P1','P2','P3'], [.065,.075,.085,.095]):
        yield dict(Pump_ID=P, D=D), t403(P, D)

def t404(F, Nf):
    P0, S0, _, noise = {'F1': (95, 18000, 18, 46), 'F2': (140, 22000, 28, 51), 'F3': (195, 26000, 42, 57)}[F]
    W, L, tb, H, tf = .180, .250, .008, .045, .0015
    s = (W - Nf * tf) / (Nf - 1); Dh = 2 * s * H / (s + H); Af = (Nf - 1) * s * H
    K = 1.45 + .085 * (L / Dh)
    V = math.sqrt(P0 / (S0 + 0.5 * 1.14 * K / Af**2)); u = V / Af
    Re = u * Dh / 1.65e-5; Nu = .023 * Re**.8 * .71**.4; h = Nu * .0268 / Dh
    mf = math.sqrt(2 * h / (205 * tf)); ef = math.tanh(mf * H) / (mf * H)
    Ae = (Nf - 1) * s * L + 2 * Nf * H * L * ef
    C = 1.14 * 1007 * V
    Rth = 1 / (C * (1 - math.exp(-h * Ae / C))) + tb / (205 * W * L)
    Tb = 35 + 720 * Rth; m = 2700 * L * (W * tb + Nf * H * tf)
    vals = dict(D_h=Dh * 1000, V_dot=V, Re_Dh=Re, h=h, eta_f=ef, A_eff=Ae, R_th=Rth, T_b=Tb, m_sink=m)
    req = dict(R1=noise <= 53, R2=Re >= 2300, R3=True, R4=Tb <= 70.0, R5=m <= 2.60)
    return vals, req
def space404():
    for F, N in itertools.product(['F1','F2','F3'], [26,30,34,38,42]):
        yield dict(Fan_ID=F, N_f=N), t404(F, N)

def t405(S, Gd):
    Do, t = {'S1': (160, 6), 'S2': (180, 6), 'S3': (180, 8), 'S4': (200, 6), 'S5': (200, 8)}[S]
    sy, cm = {'G1': (275, 2.40), 'G2': (355, 2.85), 'G3': (460, 3.50)}[Gd]
    Do_m, Di_m = Do / 1000, (Do - 2 * t) / 1000
    A = math.pi / 4 * (Do_m**2 - Di_m**2); I = math.pi / 64 * (Do_m**4 - Di_m**4); J = 2 * I; Z = 2 * I / Do_m
    E, G, L, e, P = 210e9, 80.8e9, 3.20, .45, 11500.0
    mb = 7850 * A * L
    My = P * L + .5 * mb * 9.81 * L; Mz = 2800 * L; M = math.hypot(My, Mz); T = P * e
    sb = M / Z; tau = T / (2 * Z); svm = math.sqrt(sb**2 + 3 * tau**2) / 1e6
    dv = 1000 * (P * L**3 / (3 * E * I) + mb * 9.81 * L**3 / (8 * E * I) + e * T * L / (G * J))
    k = 1 / (L**3 / (3 * E * I) + e**2 * L / (G * J)); f1 = math.sqrt(k / (P / 9.81 + .24 * mb)) / (2 * math.pi)
    cost = cm * mb
    vals = dict(m_b=mb, M_root=M, sigma_vm=svm, delta_v=dv, f_1=f1, Cost=cost)
    req = dict(R1=(Do / t) <= .068 * (210000 / sy), R2=svm <= sy / 1.5, R3=dv <= 39.0, R4=f1 >= 2.50, R5=cost <= 285.0)
    return vals, req
def space405():
    for S, Gd in itertools.product(['S1','S2','S3','S4','S5'], ['G1','G2','G3']):
        yield dict(Section_ID=S, Grade_ID=Gd), t405(S, Gd)

MODELS = {'T4-01': (t401, space401, ['Motor_ID','R','z1','z2']), 'T4-02': (t402, space402, ['MOSFET_ID','Inductor_ID','f_sw','N_c']),
          'T4-03': (t403, space403, ['Pump_ID','D']), 'T4-04': (t404, space404, ['Fan_ID','N_f']), 'T4-05': (t405, space405, ['Section_ID','Grade_ID'])}

v401, _ = t401('M2', .14, 19, 95)
print("===== T4-01 (dropped): its reference (M2, R 0.14, z1 19, z2 95) gives v_act = %.2f m/s against 0.42 m/s;" % v401['v_act'],
      "feasible designs:", sum(1 for d, (v, r) in space401() if all(r.values())), "of", sum(1 for _ in space401()))
for cid, (fn, space, keys) in MODELS.items():
    if cid not in items:
        continue
    o = items[cid]
    print(f"\n===== {cid} ({o['domain']})")
    for label, design in [('reference', o['reference_design'])] + [(f"wrong{j+1} claims {w['failed_requirements']}", w['values']) for j, w in enumerate(o['wrong_designs'])]:
        vals, req = fn(*[design[k] for k in keys])
        failed = [r for r, ok in req.items() if not ok]
        diffs = {k: (round(vals[k], 4), design.get(k)) for k in vals if k in design and isinstance(design.get(k), (int, float)) and abs(vals[k] - design[k]) > max(0.02 * abs(vals[k]), 0.011)}
        print(f"  {label}: fails {failed}; stated values off by >2%: {diffs}")
    feas = [(d, v) for d, (v, r) in space() if all(r.values())]
    n = sum(1 for _ in space())
    print(f"  design space {n}; feasible {len(feas)}: {[tuple(d.values()) for d,_ in feas[:12]]}{' ...' if len(feas) > 12 else ''}")

# ---- T4-06 (F2): physics from the corpus pages, never the pinned choices in its checks
def t406(pipe, filt, pump, fz):
    rho, cp, mu, Pv = 1200.0, 2000.0, 2.40e-3, 22.0         # KryoSol-45 at the 40.0 degC mean (Rule 1.1)
    Qh = 3600 * (144000 / (cp * 10.0)) / rho                 # m3/h, exactly 10.0 K rise (repaired wording)
    Q = Qh / 3600
    D = {'VT-32': .032, 'VT-40': .040, 'VT-50': .050, 'VT-65': .065}[pipe]
    rating, Qmax, Cf, Bf = {'FC-100': (3, 18.0, .80, .040), 'FC-200': (5, 25.0, .50, .025), 'FC-250': (10, 30.0, .30, .015), 'FC-300': (5, 35.0, .35, .015)}[filt]
    QB, H0, AH, N0, AN, emax, ke = {'VX-100': (12.0, 22.0, .0350, 1.10, .0030, .720, .55), 'VX-200': (20.0, 32.5, .0155, 1.35, .0018, .760, .50),
                                    'VX-300': (32.0, 44.0, .0080, 1.80, .0010, .790, .45), 'VX-400': (45.0, 55.0, .0050, 2.30, .0006, .810, .45)}[pump]
    s = fz / 50
    v = Q / (3.14159265 * (D / 2)**2); Re = rho * v * D / mu; f = .3164 / Re**.25
    q = .5 * rho * v**2
    dp_pipe = (f * 80.0 / D + 14.0) * q / 1000; dp_suc = (f * 8.0 / D + 2.50) * q / 1000
    dp_filt = 2.0 * (Cf * (mu / .001) * Qh + Bf * (rho / 1000) * Qh**2)
    Hsys = (dp_pipe + 65.0 + dp_filt) * 1000 / (rho * 9.81); Hp = H0 * s**2 - AH * Qh**2
    NPa = (95.0 - Pv - dp_suc) * 1000 / (rho * 9.81) - 0.50; NPr = N0 * s**1.5 + AN * Qh**2
    ew = emax - ke * (Qh / (QB * s) - 1)**2; ep = (1 - .05 * (mu / .001 - 1)) * ew
    P = rho * 9.81 * Q * Hp / (1000 * ep)
    vals = dict(volumetric_flow_m3_h=Qh, fluid_velocity_m_s=v, reynolds_number=Re, fouled_filter_dp_kPa=dp_filt,
                total_system_head_m=Hsys, pump_available_head_m=Hp, npsh_available_m=NPa, pump_shaft_power_kW=P)
    req = dict(R1=2.00 <= v <= 3.20 and 4000 <= Re <= 1e5, R2=rating <= 5 and Qmax >= Qh, R3=Hp >= Hsys,
               R4=0.70 * QB * s <= Qh <= 1.20 * QB * s, R5=NPa >= 1.20 * NPr, R6=P <= 3.40)
    return vals, req
def space406():
    for p, fl, pu, fz in itertools.product(['VT-32','VT-40','VT-50','VT-65'], ['FC-100','FC-200','FC-250','FC-300'], ['VX-100','VX-200','VX-300','VX-400'], [50,55,60]):
        yield dict(selected_pipe=p, selected_filter=fl, selected_pump=pu, vfd_frequency_Hz=fz), t406(p, fl, pu, fz)
fn, space, keys = t406, space406, ['selected_pipe','selected_filter','selected_pump','vfd_frequency_Hz']
o = items['T4-06']; print(f"\n===== T4-06 ({o['domain']}, F2)")
for label, design in [('reference', o['reference_design'])] + [(f"wrong{j+1} claims {w['failed_requirements']}", w['values']) for j, w in enumerate(o['wrong_designs'])]:
    vals, req = fn(*[design[k] for k in keys])
    diffs = {k: (round(vals[k], 4), design.get(k)) for k in vals if abs(vals[k] - design[k]) > max(0.02 * abs(vals[k]), 0.011)}
    print(f"  {label}: physically fails {[r for r, ok in req.items() if not ok]}; stated values off by >2%: {diffs}")
feas = [d for d, (v, r) in space() if all(r.values())]
print(f"  design space {sum(1 for _ in space())}; feasible {len(feas)}: {[tuple(d.values()) for d in feas]}")
v, _ = t406('VT-50', 'FC-300', 'VX-200', 55)
print("  reference margins: head %.2f%%, NPSH %.2f%%, power %.2f%%" % (100*(v['pump_available_head_m']/v['total_system_head_m']-1), 100*(v['npsh_available_m']/(1.2*(1.35*1.1**1.5+.0018*v['volumetric_flow_m3_h']**2))-1), 100*(1-v['pump_shaft_power_kW']/3.40)))
