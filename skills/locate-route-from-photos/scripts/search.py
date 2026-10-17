import math
import numpy as np
from common import Z, W, N, R, elev

AZS = np.arange(0, 360, 0.25)
DS = np.geomspace(60, 40000, 420)
SH = np.arange(1440)


def skyline(la, lo, above=2):
    # Max elevation angle per azimuth, with curvature + refraction.
    h0 = elev(la, lo) + above
    c = math.cos(math.radians(la))
    a = np.radians(AZS)[:, None]
    lats = la + DS * np.cos(a) / 111132.0
    lons = lo + DS * np.sin(a) / (111320.0 * c)
    i = np.clip(((N - lats) / R).astype(int), 0, Z.shape[0] - 1)
    j = np.clip(((lons - W) / R).astype(int), 0, Z.shape[1] - 1)
    z = np.nan_to_num(Z[i, j], nan=-1e9)
    # -0.87*DS^2/12742000: earth curvature net of atmospheric refraction (R=6371 km).
    return np.degrees(np.arctan2((z - h0) * 0.3048 - 0.87 * DS ** 2 / 12742000, DS)).max(1)


def photo_profile(P, Wimg, fov):
    # Traced px -> (azimuth offset, elevation) for an assumed FOV.
    f = (Wimg / 2) / math.tan(math.radians(fov / 2))
    xs = np.array([p[0] for p in P], float)
    ys = np.array([p[1] for p in P], float)
    az = np.degrees(np.arctan((xs - Wimg / 2) / f))
    el = -np.degrees(np.arctan((ys - ys.mean()) / np.hypot(f, xs - Wimg / 2)))
    return az, el


def match(sky, az, el):
    # Best heading; RMS after removing unknown camera tilt.
    idx = (SH[:, None] + np.round(az / 0.25).astype(int)[None, :]) % 1440
    v = sky[idx] - el[None, :]
    v -= v.mean(1, keepdims=True)
    e = np.sqrt((v ** 2).mean(1))
    k = int(e.argmin())
    return float(e[k]), k * 0.25
