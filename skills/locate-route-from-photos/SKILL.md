---
name: "locate-route-from-photos"
description: "Identify where a ski tour, hike or mountain bike ride happened by matching photo skylines to elevation data, then rebuild the likely route from terrain, treeline, trails, and the trip's distance and vert."
---

# Locate a ski tour, hike or bike route from photos

Use this when the user shares photos from an outing (often someone else's social post) and wants to know which mountains are in them, where they were taken, and what route was done: backcountry ski tour, hike/scramble, trail run, or mountain bike ride.

The method: form area hypotheses from context, fetch a real elevation model (DEM), land-cover data for treeline and, for hikes and rides, trail data; search for the camera spots that reproduce each photo's skyline; verify by rendering; then fit a route through the verified spots that matches the stated distance and vert, using the travel rules for that activity.

## Principles (learned the hard way)

- **Don't name peaks from looks alone.** Rounded alpine peaks look alike. Give a hedged area guess at most until terrain data confirms it.
- **A good score is not a match.** Always render the matched view and compare it to the photo by eye. Scores get fooled by a nearby rise that fits the curve, foreground terrain blocking the view, or cloud hiding a summit.
- **Photos must agree with each other.** All matched spots must lie on one route that fits the stated distance and vert. A strong match far from the rest is a drive-in photo or a false match; say which.
- **Treeline varies.** Never assume one number. It shifts with latitude, continentality, aspect and local wind; compute it for the area (Step 3).
- **Use every clue, not only skylines** (see the activity sections).
- **Correct yourself openly** when a new constraint breaks an earlier answer.
- **Safety and access:** the output is a reconstruction, not GPS. Say so, flag hazards for the activity, and say parking, land access and trail legality are unverified.

## Step 1: Gather context and form hypotheses

Ask for (or collect): all photos, activity type, distance and vert, loop / out-and-back / point-to-point (shuttle), date and rough time of day, and place hints (account name, caption, home town, tagged location, Strava/Garmin title). Moving time bounds distance and hints at terrain difficulty.

For each photo note: distant skyline (usable for matching), roads and their type, trails, signs, cairns, lakes, buildings, power lines, **where the photographer is relative to trees** (deep forest / forest edge / scattered krummholz / open tundra), the forest edge on distant slopes, vegetation (aspen vs conifer, wildflowers), snowfields and their aspect, track direction, shadows.

**Shadows as a compass:** with date and approximate time, compute sun azimuth (code in Step 6). A shadow pointing straight ahead means the camera faces away from the sun.

Turn the hypotheses into a bounding box (lat/lon), generous enough to include every peak that could appear on the skylines (~30–40 km around the candidate area).

## Step 2: Fetch the data automatically

Never ask the user to find data by hand first. Compute what's needed from the bounding box and fetch it.

### Elevation (required)

Try these public, no-login sources in order. Only the needed window is read.

| Source | Coverage | URL pattern (tile naming) |
|---|---|---|
| USGS 3DEP 1 arc-second (bare earth) | US | `https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1/TIFF/current/n{NN}w{WWW}/USGS_1_n{NN}w{WWW}.tif` — NN = floor(lat)+1, WWW = ceil(−lon) (**north-west** corner) |
| Copernicus GLO-30 (surface, includes canopy) | Global | `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{N|S}{lat:02d}_00_{E|W}{lon:03d}_00_DEM/Copernicus_DSM_COG_10_{N|S}{lat:02d}_00_{E|W}{lon:03d}_00_DEM.tif` — **south-west** corner |
| SRTM (AWS terrain tiles) | 60°S–60°N | `https://s3.amazonaws.com/elevation-tiles-prod/skadi/N{lat:02d}/N{lat:02d}W{lon:03d}.hgt.gz` — south-west corner |

```python
# fetch_dem.py: read only the bbox window from remote COG tiles and save dem.npz (feet)
import math, numpy as np, rasterio
from rasterio.merge import merge
def usgs_url(lat_sw,lon_sw):
    n,w=lat_sw+1,-lon_sw
    return f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1/TIFF/current/n{n:02d}w{w:03d}/USGS_1_n{n:02d}w{w:03d}.tif"
def cop_url(lat_sw,lon_sw):
    ns='N' if lat_sw>=0 else 'S'; ew='E' if lon_sw>=0 else 'W'
    t=f"Copernicus_DSM_COG_10_{ns}{abs(lat_sw):02d}_00_{ew}{abs(lon_sw):03d}_00_DEM"
    return f"https://copernicus-dem-30m.s3.amazonaws.com/{t}/{t}.tif"
def fetch(W,S,E,N,maker,out='dem.npz'):
    tiles=[(la,lo) for la in range(math.floor(S),math.floor(N)+1) for lo in range(math.floor(W),math.floor(E)+1)]
    srcs=[rasterio.open('/vsicurl/'+maker(la,lo)) for la,lo in tiles]
    arr,tr=merge(srcs,bounds=(W,S,E,N))
    z=arr[0].astype('float32'); z[z<-1000]=np.nan
    np.savez_compressed(out,z=z*3.28084,W=W,N=N,res=tr.a)
    return z.shape
# US: fetch(W,S,E,N,usgs_url); elsewhere fetch(...,cop_url)
```

Set `GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR` and `CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif` to keep remote reads fast.

### Land cover for treeline

ESA WorldCover 10 m (global, public COG, 3°×3° tiles named by the south-west corner on a multiple of 3). Class 10 = tree cover.

```python
def worldcover_url(lat,lon):
    la=math.floor(lat/3)*3; lo=math.floor(lon/3)*3
    ns='N' if la>=0 else 'S'; ew='E' if lo>=0 else 'W'
    return ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
            f"ESA_WorldCover_10m_2021_v200_{ns}{abs(la):02d}{ew}{abs(lo):03d}_Map.tif")
# Read the bbox window with rasterio (/vsicurl/), then resample to the DEM grid by
# fraction: average (wc==10) over each DEM cell -> tree_frac in [0,1].
```

### Trails (needed for hikes and rides, useful for skin tracks)

```bash
curl -s https://overpass-api.de/api/interpreter --data-urlencode 'data=[out:json][timeout:60];way["highway"~"path|track|footway|bridleway|cycleway|unclassified|service"](S,W,N,E);(._;>;);out;' > trails.json
```

For bikes also fetch US Wilderness (bikes banned): `relation["boundary"="protected_area"]["protect_class"="1b"](S,W,N,E);`.

### If the network blocks these hosts

Test once (connection refused / proxy rejection), don't try other routes, and give the user both options in one message:
1. **Allow the hosts** so it works automatically from now on: `prd-tnm.s3.amazonaws.com`, `copernicus-dem-30m.s3.amazonaws.com`, `s3.amazonaws.com`, `esa-worldcover.s3.eu-central-1.amazonaws.com`, `overpass-api.de`. On claude.ai this is under Settings → Capabilities (individual paid plans) or Organization settings → Capabilities (Team/Enterprise admins). Then retry.
2. **Download and attach**: list the exact tile URLs computed above as clickable links (USGS tiles ~50 MB; WorldCover tiles are large, so suggest clipping). If a file is over the upload limit, have them clip it in QGIS (Build Virtual Raster → Clip Raster by Extent, DEFLATE) or with `gdalbuildvrt` + `gdal_translate -projwin W N E S -co COMPRESS=DEFLATE`, using the bbox you give them. For trails: overpass-turbo.eu (Export → GeoJSON), or GPX from Trailforks, MTB Project, AllTrails, CalTopo or Gaia.

USGS US Topo GeoPDFs are a useful extra if the user has them: `pdftotext -layout` for names; `pdftoppm -r 150 -x -y -W -H` for crops; the green tint shows forest. They are not elevation grids.

Install: `pip install --break-system-packages rasterio scipy matplotlib pillow networkx`.

## Step 3: Validate the DEM and compute treeline

```python
# common.py
import numpy as np
d=np.load('dem.npz'); Z=d['z']; W=float(d['W']); N=float(d['N']); R=float(d['res'])
def elev(la,lo):
    i=(N-la)/R; j=(lo-W)/R; i0,j0=int(i),int(j); a,b=i-i0,j-j0; q=Z[i0:i0+2,j0:j0+2]
    return q[0,0]*(1-a)*(1-b)+q[0,1]*(1-a)*b+q[1,0]*a*(1-b)+q[1,1]*a*b
def peak(la0,la1,lo0,lo1):   # highest point in a box -> (lat,lon,ft)
    i0,j0=int((N-la1)/R),int((lo0-W)/R); i1,j1=int((N-la0)/R),int((lo1-W)/R)
    w=Z[i0:i1,j0:j1]; k=np.nanargmax(w); a,b=divmod(k,w.shape[1])
    return N-(i0+a)*R, W+(j0+b)*R, float(w[a,b])
```

Validate: look up several known summits with `peak()` in tight boxes and confirm elevations within ~20 ft (Copernicus reads a few meters high in forest). Use the DEM's summit location, and keep boxes small so a higher neighbour doesn't win.

### Treeline, computed locally

Treeline is not one number. It drops ~100–150 m per degree of latitude, sits higher in big continental ranges than near the coast, runs higher on sun-facing slopes in cold climates, and is pushed down by wind, avalanche paths, burns and cold-air pockets. Compute a local value per block and aspect, in this order of preference:

**A. From land cover (best).** With `tree_frac` on the DEM grid:

```python
import numpy as np, math
from scipy.ndimage import gaussian_filter
def treeline_blocks(Z_ft, tree_frac, res_deg, block_km=5, bin_ft=50, min_px=40):
    dy=res_deg*111132; dx=dy*math.cos(math.radians(LAT0))
    gy,gx=np.gradient(gaussian_filter(Z_ft*0.3048,1),dy,dx)
    slope=np.degrees(np.arctan(np.hypot(gx,gy)))
    aspect=(np.degrees(np.arctan2(-gx,gy))+180)%360          # downslope-facing direction, 0=N
    sector=((aspect+45)//90).astype(int)%4                   # 0 N,1 E,2 S,3 W
    ok=(slope>3)&(slope<38)                                  # skip flats (lakes/meadows) and cliffs
    nb=int(block_km*1000/dy); out=[]
    for r0 in range(0,Z_ft.shape[0],nb):
        for c0 in range(0,Z_ft.shape[1],nb):
            for s in range(4):
                m=ok[r0:r0+nb,c0:c0+nb]&(sector[r0:r0+nb,c0:c0+nb]==s)
                z=Z_ft[r0:r0+nb,c0:c0+nb][m]; t=tree_frac[r0:r0+nb,c0:c0+nb][m]
                if z.size<500: continue
                bins=np.arange(z.min()//bin_ft*bin_ft, z.max()+bin_ft, bin_ft)
                idx=np.digitize(z,bins); frac=[]
                for k in range(1,len(bins)):
                    sel=idx==k; frac.append(t[sel].mean() if sel.sum()>=min_px else np.nan)
                frac=np.array(frac)
                # top-down: first bin (from the top) where forest is sustained >=25% for 2 bins
                tl=np.nan
                for k in range(len(frac)-2,0,-1):
                    if frac[k]>=0.25 and frac[k-1]>=0.25: tl=bins[k+1]; break
                if not np.isnan(tl) and tl<z.max()-200:              # block actually reaches above trees
                    out.append((r0+nb/2,c0+nb/2,s,tl))
    return out   # interpolate (per sector) to a TL grid; report median and spread per aspect
```

Also record the **tree limit** (where fraction falls below ~5%, scattered krummholz) above the forest line. Present both: "forest edge ~11,650 ft (N aspects ~11,500, S ~11,800); scattered trees to ~11,900 ft." Ignore blocks whose top barely exceeds the forest (no real treeline there), and mention when ski runs, burns or avalanche paths make a block noisy.

**B. From canopy height (if WorldCover is unavailable but both DEMs are).** Copernicus is a surface model, USGS is bare earth: `canopy = cop_m − usgs_m`; cells with canopy > 4 m are forest. Use that mask in place of `tree_frac` (coarser and noisier; say so).

**C. From the photos (always use as a cross-check, and as the fallback).** After a skyline match is verified (Step 7), mark a few points on the forest edge of a distant slope in the photo. For each, turn the pixel into an azimuth and elevation angle with the matched heading/FOV, march that ray over the DEM, and take the elevation where it first hits terrain:

```python
def ray_hit(la,lo,az_deg,el_deg,above=2):
    from common import elev; import math
    h0=elev(la,lo)+above
    for d in np.geomspace(50,40000,3000):
        pla=la+d*math.cos(math.radians(az_deg))/111132; plo=lo+d*math.sin(math.radians(az_deg))/(111320*math.cos(math.radians(la)))
        if (elev(pla,plo)-h0)*0.3048 >= d*math.tan(math.radians(el_deg)) - 0.87*d*d/12742000:
            return pla,plo,elev(pla,plo)
```

The median of those elevations is the treeline that day on those slopes. Also, the photographer's own position (forest edge / krummholz / open tundra) gives a direct check on any candidate camera spot.

**D. Last resort, rough regional ranges** (state that they are rough): Colorado Rockies ~11,000–12,000 ft; northern Wyoming/Montana Rockies ~9,000–10,500 ft; Sierra Nevada ~10,000–11,500 ft; Cascades ~6,000–7,500 ft; Wasatch ~10,000–11,000 ft; Alps ~1,900–2,300 m; ask the user if they know local treeline.

Use the local treeline grid everywhere downstream: renderer colours, plausibility of camera spots (a photo taken in open tundra can't be 300 m below local treeline), and the route map's treeline line.

## Step 4: Trace each usable photo's skyline

Automatic sky detection breaks with clouds, haze and snow. Trace by hand:
1. Save a crop with a 50/100 px grid overlaid and view it.
2. Write ~15–25 (x,y) points along the far skyline, skipping foreground ridges, trees and cloud-covered parts.
3. Draw the polyline back on the photo and view it to confirm it follows the ridgeline before searching.

Crop social-media UI out of screenshots and record the image width used.

## Step 5: Use treeline to narrow camera spots

From each photo's tree context, set an elevation band relative to the **local** treeline grid: deep forest = well below TL; forest edge = TL ± 300 ft; krummholz = TL to tree limit; open tundra = above tree limit. Use this band to limit the search in Step 6, but loosen it if nothing matches.

## Step 6: Skyline search

```python
# search.py
import numpy as np, math
from common import *
AZS=np.arange(0,360,0.25); DS=np.geomspace(60,40000,420)
def skyline(la,lo,above=2):              # max elevation angle per azimuth
    h0=elev(la,lo)+above; c=math.cos(math.radians(la)); a=np.radians(AZS)[:,None]
    lats=la+DS*np.cos(a)/111132.0; lons=lo+DS*np.sin(a)/(111320.0*c)
    i=np.clip(((N-lats)/R).astype(int),0,Z.shape[0]-1); j=np.clip(((lons-W)/R).astype(int),0,Z.shape[1]-1)
    z=np.nan_to_num(Z[i,j],nan=-1e9)
    return np.degrees(np.arctan2((z-h0)*0.3048-0.87*DS**2/12742000,DS)).max(1)  # curvature + refraction
def photo_profile(P,Wimg,fov):           # traced px -> (azimuth offset, elevation) for an assumed FOV
    f=(Wimg/2)/math.tan(math.radians(fov/2)); xs=np.array([p[0] for p in P],float); ys=np.array([p[1] for p in P],float)
    return np.degrees(np.arctan((xs-Wimg/2)/f)), -np.degrees(np.arctan((ys-ys.mean())/f))
SH=np.arange(1440)
def match(sky,az,el):                   # best heading; RMS after removing unknown camera tilt
    idx=(SH[:,None]+np.round(az/0.25).astype(int)[None,:])%1440
    v=sky[idx]-el[None,:]; v-=v.mean(1,keepdims=True); e=np.sqrt((v**2).mean(1)); k=int(e.argmin())
    return float(e[k]), k*0.25
```

Grid-search candidate camera spots (start ~300 m spacing over ~40×50 km, inside the treeline band from Step 5), for FOVs 15–80° (phone main camera ≈ 65–70°; zoomed or cropped shots 15–30°). Score = RMS / skyline relief so flat skylines don't win. ~100k evaluations take ~4–5 min; run under `timeout 590`. Refine on a ~70–100 m grid around clusters and along candidate trails. Look for **clusters**, not single winners. For hikes and rides, also score points sampled along the trail network directly.

If date and time are known, drop headings that contradict the shadows:

```python
def sun_azimuth(lat,lon,utc):            # utc datetime -> (azimuth deg from N, altitude deg)
    import math
    d=utc.timetuple().tm_yday; h=utc.hour+utc.minute/60
    g=2*math.pi/365*(d-1+(h-12)/24)
    decl=0.006918-0.399912*math.cos(g)+0.070257*math.sin(g)-0.006758*math.cos(2*g)+0.000907*math.sin(2*g)
    eqt=229.18*(0.000075+0.001868*math.cos(g)-0.032077*math.sin(g)-0.014615*math.cos(2*g)-0.040849*math.sin(2*g))
    ha=math.radians(((h*60+eqt+4*lon)/4)-180); la=math.radians(lat)
    zen=math.acos(math.sin(la)*math.sin(decl)+math.cos(la)*math.cos(decl)*math.cos(ha))
    az=math.degrees(math.atan2(math.sin(ha),math.cos(ha)*math.sin(la)-math.tan(decl)*math.cos(la)))+180
    return az%360, 90-math.degrees(zen)
```

## Step 7: Render and verify

Write a renderer that ray-marches the DEM per azimuth column (near→far), shades by sun angle, colours each terrain point by the **local treeline grid** (forest below TL, grey band to tree limit, snow or rock above), fades with distance, and labels known peaks with distance. Render the best spot at the matched heading and FOV with the vertical range set around the skyline angle, and stack it under the photo at the same width. Accept a match only when the shape, the left/right order of features, the middle-ground structure and the forest edges agree. Render at least one rival spot so the user can see why it lost. Then run the photo treeline cross-check (Step 3C).

To name the summit forming the skyline, march along the centre azimuth, take the point of highest elevation angle, then `peak()` around it.

## Step 8: Fit the route (activity-specific)

First mark all verified photo spots on a map and check they can sit on one route within the stated distance. Then use the rules for the activity.

### Backcountry ski / splitboard
- Travel is off-trail. Route on the DEM grid with Dijkstra:
  - **Skin cost:** length × (1 + max(0, grade−15°)²/20 + 8 if slope>30° + 40 if slope>35°).
  - **Ski-down cost:** length; heavily penalize any climbing.
- Features: crest lines (step along the ridge taking local max), concave gullies (negative Laplacian of a smoothed DEM, 22–38°, lee aspect, just below a crest) where wind lips form, local treeline.
- Ski tracks without a parallel skin track suggest a loop.
- Hazards: show slope shading (30–35 / 35–40 / 40–45 / >45°), flag wind-loaded lee slopes and terrain above treeline, point to the regional avalanche forecast (Colorado: CAIC).

### Hiking, scrambling, trail running
- People stay on trails unless photos show otherwise (talus, cairns, class 3+ ridges). Snap candidate routes to the trail network.
- Summit or pass photos usually come from the high point; use known summits and saddles as anchor waypoints.
- Off-trail segments: Dijkstra with Tobler's hiking function as cost (speed = 6·e^(−3.5·|slope+0.05|) km/h), treating >40° as impassable except for scrambles the photos show.
- Hazards: exposure and scrambling grade, lightning above treeline in summer (give the local treeline), snowfields early season.

### Mountain biking
- Bikes are on trails and roads only, and never in designated Wilderness; drop any route that crosses it.
- Climbs: sustained grades over ~12–15% usually mean pushing; prefer fire roads and climbing trails up, singletrack down. Respect directional or bike-only descent trails if the trail data marks them.
- Far more descent than climb means a shuttle or lift; check before forcing a loop.
- Clues: berms, jumps, trail signs and markers, flow vs rocky tech, tyre tracks, e-bike rules.
- Hazards: trail closures, seasonal restrictions, private land, exposure above treeline.

### Searching loops on a trail network

```python
# Build a graph from the trail data, sample DEM gain per edge, then search loops/out-and-backs near the target.
import math, networkx as nx
from common import elev
def seg_stats(coords):                  # coords: [(lon,lat),...]
    L=G=0; prev=None
    for lo,la in coords:
        e=elev(la,lo)*0.3048
        if prev:
            L+=math.hypot((la-prev[1])*111132,(lo-prev[0])*111320*math.cos(math.radians(la)))
            G+=max(0,e-prev[2])
        prev=(lo,la,e)
    return L,G
# nodes = intersections/endpoints; edges store length and gain in BOTH directions.
# Enumerate cycles through the start node (DFS with a length cap ~1.3x target, or nx.simple_cycles on a pruned
# subgraph), score |L-Lt|/Lt + |G-Gt|/Gt, and require the route to pass within ~150 m of every verified photo spot.
```

### Distance and vert caveats
- DEM paths are shorter than real ones (switchbacks, wiggles): expect real distance 10–30% longer than a straight grid path.
- Watch and phone gain varies: barometric gain often runs higher than a 30 m DEM; GPS-only gain can be noisy. Treat a 10–15% mismatch as fine and say so.
- Report the range of routes that fit, and which parts are well-constrained (ridge, direction, summit) versus inferred (exact start, descent line).

## Step 9: Deliver

- A comparison image: each photo above its terrain render, labelled.
- A route map: hillshade, 200 ft contours, the **local treeline** line (and tree limit if distinct), trails if available, the route with direction arrows (separate styles for up and down when they differ), photo spots, start/finish, and computed vs actual distance and vert in the title. Add slope shading for ski routes.
- A GPX with the route (separate tracks for up and down if a loop) plus waypoints (start, photo spots, hazards), named "computed, unverified".
- A short reply: which peaks, where the photos were taken, the local treeline and how it was derived, the route in 3 steps, confidence and what didn't match, and the hazard and access caveats for the activity.

Send images and GPX with SendUserFile and keep working files in the scratchpad.