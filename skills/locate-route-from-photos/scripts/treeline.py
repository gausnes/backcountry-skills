import math
import numpy as np
from scipy.ndimage import gaussian_filter


def treeline_blocks(Z_ft, tree_frac, res_deg, lat0, block_km=5, bin_ft=50, min_px=40):
    dy = res_deg * 111132
    dx = dy * math.cos(math.radians(lat0))
    gy, gx = np.gradient(gaussian_filter(Z_ft * 0.3048, 1), dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    aspect = (np.degrees(np.arctan2(-gx, gy)) + 180) % 360  # downslope-facing direction, 0=N
    sector = ((aspect + 45) // 90).astype(int) % 4  # 0 N, 1 E, 2 S, 3 W
    ok = (slope > 3) & (slope < 38)  # skip flats (lakes/meadows) and cliffs
    nb = int(block_km * 1000 / dy)
    out = []
    for r0 in range(0, Z_ft.shape[0], nb):
        for c0 in range(0, Z_ft.shape[1], nb):
            for s in range(4):
                m = ok[r0:r0 + nb, c0:c0 + nb] & (sector[r0:r0 + nb, c0:c0 + nb] == s)
                z = Z_ft[r0:r0 + nb, c0:c0 + nb][m]
                t = tree_frac[r0:r0 + nb, c0:c0 + nb][m]
                if z.size < 500:
                    continue
                bins = np.arange(z.min() // bin_ft * bin_ft, z.max() + bin_ft, bin_ft)
                idx = np.digitize(z, bins)
                frac = []
                for k in range(1, len(bins)):
                    sel = idx == k
                    frac.append(t[sel].mean() if sel.sum() >= min_px else np.nan)
                frac = np.array(frac)
                # Top-down: first bin (from the top) where forest is sustained >=25% for 2 bins.
                tl = np.nan
                for k in range(len(frac) - 2, 0, -1):
                    if frac[k] >= 0.25 and frac[k - 1] >= 0.25:
                        tl = bins[k + 1]
                        break
                if not np.isnan(tl) and tl < z.max() - 200:  # block actually reaches above trees
                    out.append((r0 + nb / 2, c0 + nb / 2, s, tl))
    return out  # interpolate (per sector) to a TL grid; report median and spread per aspect
