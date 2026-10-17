# Vortexia Fluidics Engineering Manual — Section 3: VX-Pump Centrifugal Pumps & VFD Drives

# 4. VX-Pump Series Catalogue (Reference Speed $f_0 = 50\text{ Hz}$)

Allowed discrete VFD frequency settings: $f_{\text{VFD}} \in \{50, 55, 60\}\text{ Hz}$. Define speed ratio $s = f_{\text{VFD}} / 50$.

| Pump Model | $Q_{\text{BEP,50}}$ ($\text{m}^3/\text{h}$) | Shutoff Head $H_0$ ($\text{m}$) | Head Coeff $A_H$ ($\text{m}/(\text{m}^3/\text{h})^2$) | Base NPSH $N_0$ ($\text{m}$) | NPSH Coeff $A_N$ ($\text{m}/(\text{m}^3/\text{h})^2$) | Peak Water Eff $\eta_{\max}$ (-) | Eff Roll-off $k_\eta$ (-) |
|---|---|---|---|---|---|---|---|---|
| `VX-100` | 12.0 | 22.00 | 0.0350 | 1.10 | 0.0030 | 0.720 | 0.55 |
| `VX-200` | 20.0 | 32.50 | 0.0155 | 1.35 | 0.0018 | 0.760 | 0.50 |
| `VX-300` | 32.0 | 44.00 | 0.0080 | 1.80 | 0.0010 | 0.790 | 0.45 |
| `VX-400` | 45.0 | 55.00 | 0.0050 | 2.30 | 0.0006 | 0.810 | 0.45 |

**Rule 4.1 (Pump Curves and Allowable Operating Region):**
With $Q$ in $\text{m}^3/\text{h}$ and $g = 9.81\text{ m/s}^2$:
- Best efficiency flow rate at speed ratio $s$: $Q_{\text{BEP}}(s) = Q_{\text{BEP,50}} \cdot s$
- **Allowable Operating Region (AOR):** The operating flow $Q$ must satisfy $0.70 \cdot Q_{\text{BEP}}(s) \le Q \le 1.20 \cdot Q_{\text{BEP}}(s)$.
- Available pump head: $H_{\text{pump}}(Q, s) = H_0 s^2 - A_H Q^2$ (must satisfy $H_{\text{pump}} \ge H_{\text{sys}}$, where $H_{\text{sys}} = \frac{\Delta P_{\text{pipe}} + \Delta P_{\text{load}} + \Delta P_{\text{filter,fouled}}}{\rho g}$).
- Required NPSH: $NPSH_R(Q, s) = N_0 s^{1.5} + A_N Q^2$.

**Rule 4.2 (Cavitation Margin):**
Available NPSH at the pump inlet with suction lift $h_s$ (where $h_s > 0$ when pump is above tank liquid level) is:
$$NPSH_A = \frac{P_{\text{tank}} - P_v - \Delta P_{\text{suction}}}{\rho g} - h_s$$
Safe operation requires $NPSH_A \ge 1.20 \times NPSH_R$.

**Rule 4.3 (Viscosity Correction and Shaft Power):**
Clear-water efficiency is $\eta_w = \eta_{\max} - k_\eta \left(\frac{Q}{Q_{\text{BEP}}(s)} - 1\right)^2$.
For fluids with $\mu > 1.00\text{ mPa}\cdot\text{s}$, hydraulic efficiency is $\eta_p = C_\mu \cdot \eta_w$, where:
$$C_\mu = 1 - 0.05 \left(\frac{\mu}{1.00\text{ mPa}\cdot\text{s}} - 1\right)$$
Pump shaft input power (in $\text{kW}$, with discharge throttling valve absorbing $H_{\text{pump}} - H_{\text{sys}}$) is:
$$P_{\text{shaft}} = \frac{\rho g (Q / 3600) H_{\text{pump}}}{1000 \cdot \eta_p}$$
