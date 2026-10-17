import numpy as np

d = np.load('dem.npz')
Z, W, N, R = d['z'], float(d['W']), float(d['N']), float(d['res'])


def elev(la, lo):
    i = (N - la) / R
    j = (lo - W) / R
    i0, j0 = int(i), int(j)
    a, b = i - i0, j - j0
    q = Z[i0:i0 + 2, j0:j0 + 2]
    return q[0, 0] * (1 - a) * (1 - b) + q[0, 1] * (1 - a) * b + q[1, 0] * a * (1 - b) + q[1, 1] * a * b


def peak(la0, la1, lo0, lo1):
    # Highest point in a box -> (lat, lon, ft). Keep boxes small so a higher neighbour doesn't win.
    i0, j0 = int((N - la1) / R), int((lo0 - W) / R)
    i1, j1 = int((N - la0) / R), int((lo1 - W) / R)
    w = Z[i0:i1, j0:j1]
    k = np.nanargmax(w)
    a, b = divmod(k, w.shape[1])
    return N - (i0 + a) * R, W + (j0 + b) * R, float(w[a, b])
