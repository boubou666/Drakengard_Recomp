"""Symbolize zz_sampling_profiler output with the MSVC linker map file.
usage: symbolize_profile.py <map> <profile> [top]"""
import bisect, re, sys
from collections import Counter, defaultdict

mapPath, profPath = sys.argv[1], sys.argv[2]
import struct, os
exePath = os.path.splitext(mapPath)[0] + ".exe"
pe = open(exePath, "rb").read(4096)
peOff = struct.unpack_from("<I", pe, 0x3C)[0]
imageSize = struct.unpack_from("<I", pe, peOff + 24 + 56)[0]
top = int(sys.argv[3]) if len(sys.argv) > 3 else 25
base = 0x140000000
syms = []
for line in open(mapPath, errors="replace"):
    m = re.match(r"\s*[0-9a-fA-F]{4}:[0-9a-fA-F]{8}\s+(\S+)\s+([0-9a-fA-F]{16})\s", line)
    if m:
        if "Preferred load address" in line:
            continue
        syms.append((int(m.group(2), 16) - base, m.group(1)))
    elif "Preferred load address is" in line:
        base = int(line.split()[-1], 16)
syms.sort()
addrs = [a for a, _ in syms]

def name(rva):
    i = bisect.bisect_right(addrs, rva) - 1
    return syms[i][1] if i >= 0 else "?"

perThread = defaultdict(Counter)
for line in open(profPath):
    parts = line.split()
    tid, leaf, count = parts[0], int(parts[1], 16), int(parts[-1])
    caller = int(parts[2], 16) if len(parts) == 4 else 0
    if 0 < leaf < imageSize:
        label = name(leaf)
    elif 0 < caller < imageSize:
        label = "[blocked] in " + name(caller)
    else:
        label = "<outside exe>"
    perThread[tid][label] += count

for tid, counter in sorted(perThread.items(), key=lambda kv: -sum(kv[1].values())):
    total = sum(counter.values())
    if total < 500:
        continue
    print(f"=== thread {tid}: {total} samples")
    for sym, c in counter.most_common(top):
        print(f"  {100.0 * c / total:5.1f}%  {sym[:150]}")
