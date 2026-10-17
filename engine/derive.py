from __future__ import annotations

import numpy as np


def magnus_rh(t_c: np.ndarray, td_c: np.ndarray) -> np.ndarray:
    """Relative humidity % from 2 m temperature and dewpoint (°C)."""
    t = np.asarray(t_c, dtype=np.float64)
    td = np.asarray(td_c, dtype=np.float64)

    def es(temp: np.ndarray) -> np.ndarray:
        return np.exp((17.625 * temp) / (243.04 + temp))

    with np.errstate(invalid="ignore", divide="ignore"):
        rh = 100.0 * es(td) / es(t)
    return np.clip(rh, 0.0, 100.0)


def k_to_c(kelvin: np.ndarray) -> np.ndarray:
    return np.asarray(kelvin, dtype=np.float64) - 273.15


def pa_to_hpa(pa: np.ndarray) -> np.ndarray:
    return np.asarray(pa, dtype=np.float64) / 100.0


def m_to_mm(metres: np.ndarray) -> np.ndarray:
    return np.asarray(metres, dtype=np.float64) * 1000.0
