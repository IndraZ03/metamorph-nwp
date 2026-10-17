"""Fixed RGBA LUTs. Tiles are pre-colored; the app never owns visualization."""

from __future__ import annotations

import numpy as np

LUT_SIZE = 256


def _lerp(stops: list[tuple[float, tuple[int, int, int, int]]]) -> np.ndarray:
    """stops: (t 0..1, rgba). Returns (256, 4) uint8."""
    xs = np.array([s[0] for s in stops], dtype=np.float64)
    cs = np.array([s[1] for s in stops], dtype=np.float64)
    t = np.linspace(0.0, 1.0, LUT_SIZE)
    out = np.empty((LUT_SIZE, 4), dtype=np.float64)
    for i in range(4):
        out[:, i] = np.interp(t, xs, cs[:, i])
    return np.clip(out, 0, 255).astype(np.uint8)


# RdYlBu_r-ish
_TEMP = _lerp(
    [
        (0.00, (49, 54, 149, 220)),
        (0.20, (69, 117, 180, 230)),
        (0.40, (171, 217, 233, 230)),
        (0.50, (255, 255, 191, 230)),
        (0.65, (253, 174, 97, 235)),
        (0.80, (215, 48, 39, 240)),
        (1.00, (165, 0, 38, 245)),
    ]
)

_RH = _lerp(
    [
        (0.00, (255, 255, 229, 40)),
        (0.30, (194, 230, 153, 140)),
        (0.55, (120, 198, 121, 190)),
        (0.75, (49, 163, 84, 220)),
        (1.00, (0, 104, 55, 240)),
    ]
)

_MSL = _lerp(
    [
        (0.00, (178, 24, 43, 220)),
        (0.35, (239, 138, 98, 210)),
        (0.50, (247, 247, 247, 80)),
        (0.65, (103, 169, 207, 210)),
        (1.00, (33, 102, 172, 230)),
    ]
)

_TP = _lerp(
    [
        (0.00, (199, 233, 192, 40)),
        (0.15, (161, 217, 155, 140)),
        (0.30, (65, 171, 93, 190)),
        (0.50, (8, 104, 172, 220)),
        (0.70, (8, 64, 129, 235)),
        (0.85, (136, 65, 157, 245)),
        (1.00, (197, 27, 125, 255)),
    ]
)

_CAPE = _lerp(
    [
        (0.00, (255, 255, 204, 30)),
        (0.20, (255, 237, 160, 120)),
        (0.40, (254, 178, 76, 180)),
        (0.60, (253, 141, 60, 210)),
        (0.80, (227, 26, 28, 235)),
        (1.00, (128, 0, 38, 250)),
    ]
)

_TCC = _lerp(
    [
        (0.00, (255, 255, 255, 0)),
        (0.15, (230, 230, 230, 50)),
        (0.40, (189, 189, 189, 120)),
        (0.70, (150, 150, 150, 180)),
        (1.00, (99, 99, 99, 230)),
    ]
)

_WIND = _lerp(
    [
        (0.00, (230, 245, 255, 120)),  # calm / light blue
        (0.10, (170, 220, 250, 180)),
        (0.20, (100, 200, 210, 220)),  # cyan
        (0.35, (80, 210, 120, 240)),   # green
        (0.50, (250, 225, 60, 250)),   # yellow
        (0.65, (250, 140, 40, 255)),   # orange
        (0.80, (230, 40, 40, 255)),    # red
        (1.00, (160, 20, 150, 255)),   # purple / severe
    ]
)

_UV = _lerp(
    [
        (0.00, (30, 60, 180, 255)),
        (0.50, (245, 245, 245, 255)),
        (1.00, (180, 30, 30, 255)),
    ]
)

# id -> (vmin, vmax, lut, transparent_below or None, log_scale)
SPECS: dict[str, dict] = {
    "t2m": {"vmin": -5.0, "vmax": 35.0, "lut": _TEMP, "hide_below": None, "log": False},
    "d2m": {"vmin": 0.0, "vmax": 28.0, "lut": _TEMP, "hide_below": None, "log": False},
    "rh": {"vmin": 0.0, "vmax": 100.0, "lut": _RH, "hide_below": None, "log": False},
    "msl": {"vmin": 990.0, "vmax": 1030.0, "lut": _MSL, "hide_below": None, "log": False},
    "tp": {"vmin": 0.1, "vmax": 300.0, "lut": _TP, "hide_below": 0.1, "log": True},
    "cape": {"vmin": 50.0, "vmax": 4000.0, "lut": _CAPE, "hide_below": 50.0, "log": False},
    "tcc": {"vmin": 0.0, "vmax": 1.0, "lut": _TCC, "hide_below": 0.02, "log": False},
    "wind10m": {"vmin": 0.0, "vmax": 30.0, "lut": _WIND, "hide_below": None, "log": False},
    "u10": {"vmin": -25.0, "vmax": 25.0, "lut": _UV, "hide_below": None, "log": False},
    "v10": {"vmin": -25.0, "vmax": 25.0, "lut": _UV, "hide_below": None, "log": False},
}


def colorize(values: np.ndarray, var_id: str) -> np.ndarray:
    """values (H, W) float → RGBA (H, W, 4) uint8."""
    spec = SPECS[var_id]
    v = np.asarray(values, dtype=np.float64)
    rgba = np.zeros(v.shape + (4,), dtype=np.uint8)

    valid = np.isfinite(v)
    hide = spec["hide_below"]
    if hide is not None:
        valid = valid & (v >= hide)

    vmin, vmax = spec["vmin"], spec["vmax"]
    if spec["log"]:
        vv = np.clip(v, vmin, vmax)
        t = (np.log10(vv) - np.log10(vmin)) / (np.log10(vmax) - np.log10(vmin))
    else:
        t = (v - vmin) / (vmax - vmin)
    t = np.clip(t, 0.0, 1.0)
    t = np.where(valid, t, 0.0)
    idx = np.clip(np.nan_to_num(t, nan=0.0) * (LUT_SIZE - 1), 0, LUT_SIZE - 1).astype(np.int32)
    lut = spec["lut"]
    rgba[valid] = lut[idx[valid]]
    return rgba


NUMERIC_OFFSET = 1000.0
NUMERIC_SCALE = 10.0


def encode_numeric_rgba(data_array: np.ndarray) -> np.ndarray:
    """Terrain-RGB-like: val = ((R<<16 | G<<8 | B) / 10) - 1000. Alpha 0 = nodata."""
    h, w = data_array.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    valid = np.isfinite(data_array)
    if not np.any(valid):
        return rgba
    val_int = np.clip(
        (data_array[valid] + NUMERIC_OFFSET) * NUMERIC_SCALE, 0, 16777215
    ).astype(np.uint32)
    rgba[valid, 0] = ((val_int >> 16) & 255).astype(np.uint8)
    rgba[valid, 1] = ((val_int >> 8) & 255).astype(np.uint8)
    rgba[valid, 2] = (val_int & 255).astype(np.uint8)
    rgba[valid, 3] = 255
    return rgba
