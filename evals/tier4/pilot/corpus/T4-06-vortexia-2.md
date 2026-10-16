# Vortexia Fluidics Engineering Manual — Section 2: FiltraCore Duplex Inline Filters

# 3. FiltraCore Duplex Filter Catalogue

| Filter Model | Filtration Rating ($\mu\text{m}$) | Max Flow $Q_{\max}$ ($\text{m}^3/\text{h}$) | Laminar Coeff $C_f$ ($\text{kPa}/(\text{m}^3/\text{h})$) | Turbulent Coeff $B_f$ ($\text{kPa}/(\text{m}^3/\text{h})^2$) |
|---|---|---|---|---|
| `FC-100` | 3 | 18.0 | 0.80 | 0.040 |
| `FC-200` | 5 | 25.0 | 0.50 | 0.025 |
| `FC-250` | 10 | 30.0 | 0.30 | 0.015 |
| `FC-300` | 5 | 35.0 | 0.35 | 0.015 |

**Rule 3.1 (Clean and Fouled Filter Pressure Drop):**
For a fluid with dynamic viscosity $\mu$ and density $\rho$ at volumetric flow rate $Q$ (in $\text{m}^3/\text{h}$), the clean filter pressure drop (in $\text{kPa}$) is:
$$\Delta P_{\text{filter,clean}} = C_f \left(\frac{\mu}{\mu_{\text{ref}}}\right) Q + B_f \left(\frac{\rho}{\rho_{\text{ref}}}\right) Q^2$$
where $\mu_{\text{ref}} = 1.00\text{ mPa}\cdot\text{s} = 0.00100\text{ Pa}\cdot\text{s}$ and $\rho_{\text{ref}} = 1000\text{ kg/m}^3$.

**Rule 3.2 (Fouled Sizing Margin):** All system head calculations must size the pump for the end-of-life fouled filter condition:
$$\Delta P_{\text{filter,fouled}} = 2.0 \times \Delta P_{\text{filter,clean}}$$
