import math
import numpy as np
import rasterio
from rasterio.merge import merge


def usgs_url(lat_sw, lon_sw):
    n, w = lat_sw + 1, -lon_sw
    return f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1/TIFF/current/n{n:02d}w{w:03d}/USGS_1_n{n:02d}w{w:03d}.tif"


def cop_url(lat_sw, lon_sw):
    ns = 'N' if lat_sw >= 0 else 'S'
    ew = 'E' if lon_sw >= 0 else 'W'
    t = f"Copernicus_DSM_COG_10_{ns}{abs(lat_sw):02d}_00_{ew}{abs(lon_sw):03d}_00_DEM"
    return f"https://copernicus-dem-30m.s3.amazonaws.com/{t}/{t}.tif"


def fetch(W, S, E, N, maker, out='dem.npz'):
    # Saves z in feet; source tiles are in meters.
    tiles = [(la, lo) for la in range(math.floor(S), math.floor(N) + 1)
             for lo in range(math.floor(W), math.floor(E) + 1)]
    srcs = [rasterio.open('/vsicurl/' + maker(la, lo)) for la, lo in tiles]
    arr, tr = merge(srcs, bounds=(W, S, E, N))
    z = arr[0].astype('float32')
    z[z < -1000] = np.nan
    np.savez_compressed(out, z=z * 3.28084, W=W, N=N, res=tr.a)
    return z.shape


def worldcover_url(lat, lon):
    # ESA WorldCover 10 m tile covering (lat, lon); class 10 = tree cover.
    la = math.floor(lat / 3) * 3
    lo = math.floor(lon / 3) * 3
    ns = 'N' if la >= 0 else 'S'
    ew = 'E' if lo >= 0 else 'W'
    return ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
            f"ESA_WorldCover_10m_2021_v200_{ns}{abs(la):02d}{ew}{abs(lo):03d}_Map.tif")
