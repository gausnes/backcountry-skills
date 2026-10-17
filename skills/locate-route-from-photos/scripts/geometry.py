import math
import numpy as np
from common import elev


def ray_hit(la, lo, az_deg, el_deg, above=2):
    h0 = elev(la, lo) + above
    for d in np.geomspace(50, 40000, 3000):
        pla = la + d * math.cos(math.radians(az_deg)) / 111132
        plo = lo + d * math.sin(math.radians(az_deg)) / (111320 * math.cos(math.radians(la)))
        # +0.87*d^2/12742000: earth curvature net of atmospheric refraction (R=6371 km), same term as search.skyline.
        if (elev(pla, plo) - h0) * 0.3048 >= d * math.tan(math.radians(el_deg)) + 0.87 * d * d / 12742000:
            return pla, plo, elev(pla, plo)


def sun_azimuth(lat, lon, utc):
    # utc: datetime -> (azimuth deg from N, altitude deg).
    d = utc.timetuple().tm_yday
    h = utc.hour + utc.minute / 60
    g = 2 * math.pi / 365 * (d - 1 + (h - 12) / 24)
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                     - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    ha = math.radians(((h * 60 + eqt + 4 * lon) / 4) - 180)
    la = math.radians(lat)
    zen = math.acos(math.sin(la) * math.sin(decl) + math.cos(la) * math.cos(decl) * math.cos(ha))
    az = math.degrees(math.atan2(math.sin(ha), math.cos(ha) * math.sin(la) - math.tan(decl) * math.cos(la))) + 180
    return az % 360, 90 - math.degrees(zen)


def seg_stats(coords):
    # coords: [(lon, lat), ...] -> (length_m, gain_m) along the segment.
    L = G = 0
    prev = None
    for lo, la in coords:
        e = elev(la, lo) * 0.3048
        if prev:
            L += math.hypot((la - prev[1]) * 111132, (lo - prev[0]) * 111320 * math.cos(math.radians(la)))
            G += max(0, e - prev[2])
        prev = (lo, la, e)
    return L, G
