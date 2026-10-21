"""Detect vertical up/down bounce between consecutive captured frames (PS2X_CAPTURE_DIR output).
usage: jitter_check.py <capture dir>
For each consecutive pair, finds the vertical shift (-2..2 rows) that best aligns them; a run of
alternating non-zero shifts on otherwise similar frames is the 1-pixel bounce."""
import glob, os, struct, sys, zlib


def load_png_luma(path, step=4):
    data = open(path, "rb").read()
    pos, idat, width, height, bpp = 8, b"", 0, 0, 4
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", chunk[:10])
            bpp = {6: 4, 2: 3, 0: 1, 4: 2}[color]
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * bpp
    rows, prev = [], bytearray(stride)
    for y in range(height):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        rows.append([line[x * bpp] + line[x * bpp + 1] + line[x * bpp + 2] for x in range(0, width, step)])
    return rows


def best_shift(a, b):
    h = len(a)
    scores = {}
    for d in (-2, -1, 0, 1, 2):
        total = 0
        for y in range(8, h - 8, 2):
            total += sum(abs(p - q) for p, q in zip(a[y], b[y + d]))
        scores[d] = total
    d = min(scores, key=scores.get)
    return d, scores[0], scores[d]


files = sorted(glob.glob(os.path.join(sys.argv[1], "frame_*.png")))
start = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
end = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
files = [f for f in files if start <= int(os.path.basename(f)[6:-4]) / 10.0 <= end]
prev = None
out = []
for f in files:
    cur = load_png_luma(f)
    if prev is not None:
        d, e0, ed = best_shift(cur, prev)
        out.append((os.path.basename(f), d, e0, ed))
    prev = cur
alternations = 0
for i in range(1, len(out)):
    if out[i][1] != 0 and out[i][1] == -out[i - 1][1]:
        alternations += 1
for name, d, e0, ed in out:
    print(f"{name} shift={d:+d} err0={e0} errBest={ed}")
print(f"pairs={len(out)} nonzero_shifts={sum(1 for o in out if o[1])} alternating={alternations}")
