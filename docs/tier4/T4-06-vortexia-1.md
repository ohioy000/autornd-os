# Vortexia Fluidics Engineering Manual — Section 1: KryoSol-45 Coolant & VortaTube Piping

# 1. KryoSol-45 Dielectric Coolant Properties

**Rule 1.1 (Reference Temperature):** All fluid properties in a closed thermal loop must be evaluated at the arithmetic mean loop temperature $T_{\text{mean}} = \frac{1}{2}(T_{\text{in}} + T_{\text{out}})$.

| Temp ($^\circ\text{C}$) | Density $\rho$ ($\text{kg/m}^3$) | Specific Heat $c_p$ ($\text{J/(kg}\cdot\text{K)}$) | Dynamic Viscosity $\mu$ ($\text{mPa}\cdot\text{s}$) | Vapor Pressure $P_v$ ($\text{kPa(abs)}$) |
|---|---|---|---|---|
| 30.0 | 1215 | 1960 | 3.10 | 14.5 |
| 35.0 | 1208 | 1980 | 2.72 | 18.0 |
| 40.0 | 1200 | 2000 | 2.40 | 22.0 |
| 45.0 | 1192 | 2020 | 2.12 | 26.8 |
| 50.0 | 1185 | 2040 | 1.88 | 32.5 |

---

# 2. VortaTube Smooth-Bore Fluoropolymer Piping

| Model | Inner Diameter $D$ ($\text{m}$) | Max Working Pressure ($\text{kPa}$) |
|---|---|---|
| `VT-32` | 0.032 | 1000 |
| `VT-40` | 0.040 | 1000 |
| `VT-50` | 0.050 | 850 |
| `VT-65` | 0.065 | 700 |

**Rule 2.1 (Velocity Window):** In KryoSol-45 loops, bulk fluid velocity $v = \frac{Q}{\pi (D/2)^2}$ (using $\pi = 3.14159265$) must satisfy:
- $v \ge 2.00\text{ m/s}$ (to prevent micro-bubble holdup in horizontal runs)
- $v \le 3.20\text{ m/s}$ (to prevent electrostatic charge accumulation)

**Rule 2.2 (Pipe Friction Loss):** VortaTube piping is hydraulically smooth. For turbulent flow ($4000 \le Re \le 10^5$, where $Re = \frac{\rho v D}{\mu}$), the Darcy friction factor is:
$$f = \frac{0.3164}{Re^{0.25}}$$
Pressure drop across a line segment of length $L$ and minor loss coefficient sum $K$ is:
$$\Delta P = \left(f \frac{L}{D} + K\right) \frac{1}{2} \rho v^2$$
