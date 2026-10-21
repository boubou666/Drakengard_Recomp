"""Summarize a PS2X_GS_DUMP_AT primitive dump: triangle sizes in screen space and suspicious vertices."""
import re
import sys
from collections import Counter

VERTEX = re.compile(r"\(([-\d.]+),([-\d.]+),(\d+) c=(\w+) f=(\d+) stq=([^,]+),([^,]+),([^ ]+) uv=(\d+),(\d+)\)")
FIELD = re.compile(r"(\w+)=([^ |]+)")


def main(path):
    sizes = Counter()
    examples = []
    total_area = 0.0
    tri_count = 0
    q_values = Counter()
    for line in open(path):
        head, _, verts = line.partition("|")
        fields = dict(FIELD.findall(head))
        if fields.get("type") not in ("3", "4", "5"):
            continue
        ofx, ofy = map(int, fields["ofs"].strip("()").split(","))
        pts = [(float(m[0]) - ofx, float(m[1]) - ofy, m) for m in VERTEX.findall(verts)]
        if len(pts) != 3:
            continue
        tri_count += 1
        (x0, y0, _), (x1, y1, _), (x2, y2, _) = pts
        area = abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)) / 2
        total_area += min(area, 640 * 480)
        bucket = "huge(>100k)" if area > 100000 else "big(>10k)" if area > 10000 else "mid(>500)" if area > 500 else "small"
        sizes[bucket] += 1
        for _, _, m in pts:
            q_values["q<=0" if float(m[7]) <= 0 else "q>0"] += 1
        if area > 100000 and len(examples) < 12:
            examples.append(line.strip()[:600])
    print(f"triangles={tri_count} sizes={dict(sizes)} summed_area={total_area:.0f} ({total_area / (640 * 480):.1f} screens)")
    print("q:", dict(q_values))
    for example in examples:
        print(example)


if __name__ == "__main__":
    main(sys.argv[1])
