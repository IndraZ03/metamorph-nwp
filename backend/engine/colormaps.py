import numpy as np


def _interpolate_lut(stops):
    """
    Generate 256x4 RGBA uint8 LUT from color stops.
    stops: list of tuples (norm_pos (0.0..1.0), (r, g, b, a))
    """
    stops = sorted(stops, key=lambda s: s[0])
    lut = np.zeros((256, 4), dtype=np.uint8)

    positions = [int(round(s[0] * 255)) for s in stops]
    colors = [np.array(s[1], dtype=np.float32) for s in stops]

    for i in range(len(stops) - 1):
        p0, p1 = positions[i], positions[i + 1]
        c0, c1 = colors[i], colors[i + 1]
        if p1 == p0:
            lut[p0] = c0.astype(np.uint8)
            continue
        for p in range(p0, p1 + 1):
            t = (p - p0) / float(p1 - p0)
            c = (1.0 - t) * c0 + t * c1
            lut[p] = np.clip(c, 0, 255).astype(np.uint8)

    # Pad before first and after last
    if positions[0] > 0:
        lut[:positions[0]] = colors[0].astype(np.uint8)
    if positions[-1] < 255:
        lut[positions[-1]:] = colors[-1].astype(np.uint8)

    return lut


# 1. Temperature: -10 to 45 C
LUT_T_2M = _interpolate_lut([
    (0.00, (40, 20, 140, 180)),   # -10 C: deep indigo
    (0.18, (0, 150, 230, 180)),   # 0 C: cyan/blue
    (0.45, (50, 200, 80, 180)),   # 15 C: green
    (0.62, (240, 220, 20, 180)),  # 24 C: yellow
    (0.73, (255, 120, 0, 180)),   # 30 C: orange
    (0.85, (220, 30, 30, 190)),   # 37 C: red
    (1.00, (180, 0, 140, 200)),   # 45 C: magenta/purple
])

# 2. Relative Humidity: 0 to 100%
LUT_RELHUM_2M = _interpolate_lut([
    (0.00, (180, 140, 80, 0)),    # 0%: transparent
    (0.35, (160, 200, 100, 0)),   # 35%: transparent
    (0.50, (130, 210, 120, 80)),  # 50%: light green
    (0.70, (40, 180, 210, 140)),  # 70%: cyan
    (0.85, (30, 110, 220, 180)),  # 85%: blue
    (1.00, (15, 30, 180, 220)),   # 100%: deep indigo
])

# 3. Rain Accumulation: 0 to 250 mm
LUT_TOT_PREC = _interpolate_lut([
    (0.000, (0, 0, 0, 0)),         # 0 mm: fully transparent
    (0.002, (0, 0, 0, 0)),         # <0.5 mm: transparent
    (0.008, (170, 230, 255, 130)), # 2 mm: pale blue
    (0.040, (40, 180, 230, 170)),  # 10 mm: teal
    (0.100, (30, 200, 60, 200)),   # 25 mm: green
    (0.200, (255, 230, 0, 220)),   # 50 mm: yellow
    (0.400, (255, 100, 0, 235)),   # 100 mm: orange
    (0.700, (220, 20, 20, 245)),   # 175 mm: red
    (1.000, (200, 0, 200, 255)),   # 250+ mm: magenta
])

# 4. Pressure PMSL: 996 to 1020 hPa
LUT_PMSL = _interpolate_lut([
    (0.00, (100, 20, 160, 160)),  # <996: deep violet (low)
    (0.25, (20, 130, 220, 160)),  # 1002: blue/cyan
    (0.50, (110, 190, 140, 160)), # 1008: neutral tropical
    (0.75, (240, 190, 70, 160)),  # 1014: warm amber
    (1.00, (210, 50, 40, 160)),   # 1020: brick red (high)
])

# 5. Dew Point: 10 to 32 C
LUT_TD_2M = _interpolate_lut([
    (0.00, (200, 180, 130, 170)),  # 10 C: dry khaki
    (0.27, (90, 190, 130, 170)),   # 16 C: comfortable green
    (0.50, (40, 170, 220, 175)),   # 21 C: humid cyan
    (0.73, (20, 80, 210, 180)),    # 26 C: muggy blue
    (1.00, (150, 20, 180, 190)),   # 32 C: oppressive violet
])

# 6. CAPE: 0 to 4000 J/kg
LUT_CAPE_ML = _interpolate_lut([
    (0.000, (0, 0, 0, 0)),         # 0 J/kg: transparent
    (0.025, (0, 0, 0, 0)),         # <100: transparent
    (0.125, (160, 220, 120, 90)),  # 500: pale green
    (0.250, (255, 230, 50, 150)),  # 1000: yellow
    (0.500, (255, 130, 0, 200)),   # 2000: orange
    (0.750, (230, 30, 30, 230)),   # 3000: bright red
    (1.000, (255, 0, 220, 255)),   # 4000+: neon fuchsia
])

# 7. Cloud Cover: 0 to 100%
LUT_CLCT = _interpolate_lut([
    (0.00, (255, 255, 255, 0)),    # 0%: transparent
    (0.12, (255, 255, 255, 0)),    # <12%: transparent
    (0.30, (255, 255, 255, 45)),   # 30%: faint haze
    (0.60, (255, 255, 255, 110)),  # 60%: medium cloud
    (0.85, (255, 255, 255, 180)),  # 85%: thick cloud
    (1.00, (255, 255, 255, 220)),  # 100%: overcast
])

COLORMAPS = {
    "t_2m": LUT_T_2M,
    "relhum_2m": LUT_RELHUM_2M,
    "tot_prec": LUT_TOT_PREC,
    "pmsl": LUT_PMSL,
    "td_2m": LUT_TD_2M,
    "cape_ml": LUT_CAPE_ML,
    "clct": LUT_CLCT,
}


def apply_colormap(data_array, param_key, vmin, vmax):
    """
    Vectorized mapping from 2D float array to (H, W, 4) uint8 RGBA image.
    Handles NaN/missing values as transparent [0, 0, 0, 0].
    """
    lut = COLORMAPS[param_key]

    # Mask NaNs before cast
    nan_mask = np.isnan(data_array)
    norm = (data_array - vmin) / float(vmax - vmin)
    norm = np.clip(norm, 0.0, 1.0)
    norm = np.nan_to_num(norm, nan=0.0)
    idx = (norm * 255).astype(np.uint8)

    rgba = lut[idx]

    if np.any(nan_mask):
        rgba[nan_mask] = 0

    return rgba
