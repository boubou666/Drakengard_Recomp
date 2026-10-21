"""Find code the heuristic analyzer missed: J/JAL targets that are not registered
in the generated function table, and the starts of code gaps not covered by any
generated function. Prints TOML entry_points strings."""
import os
import re
import struct
import sys

elf_path, out_dir = sys.argv[1], sys.argv[2]
data = open(elf_path, "rb").read()

# Locate the executable PT_LOAD segment.
phoff = struct.unpack_from("<I", data, 28)[0]
phnum = struct.unpack_from("<H", data, 44)[0]
code_off = code_va = code_size = None
for i in range(phnum):
    p_type, p_off, p_va, _, p_filesz, _, p_flags, _ = struct.unpack_from("<8I", data, phoff + i * 32)
    if p_type == 1 and p_flags & 1:
        code_off, code_va, code_size = p_off, p_va, p_filesz
code_end = code_va + code_size


def word(addr):
    return struct.unpack_from("<I", data, code_off + addr - code_va)[0]


# Address ranges covered by generated functions (from instruction comments).
addr_re = re.compile(r"^\s*// 0x([0-9a-f]+): 0x[0-9a-f]+\s", re.M)
covered = []
for name in os.listdir(out_dir):
    if not name.endswith(".cpp") or name == "register_functions.cpp":
        continue
    addrs = [int(a, 16) for a in addr_re.findall(open(os.path.join(out_dir, name)).read())]
    if addrs:
        covered.append((min(addrs), max(addrs) + 4))
covered.sort()

# Addresses registered in the dispatch table.
registered = set(int(a, 16) for a in re.findall(
    r"g_ps2RecompiledFunctionTable\[\d+\] = [^;]+; // 0x([0-9a-f]+)",
    open(os.path.join(out_dir, "register_functions.cpp")).read()))

entries = set()

# 1) Direct J/JAL targets that are not dispatchable.
for addr in range(code_va, code_end, 4):
    w = word(addr)
    op = w >> 26
    if op in (2, 3):
        target = ((addr + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
        if code_va <= target < code_end and target not in registered:
            entries.add(target)

# 2) Start of every uncovered gap (skipping padding nops).
cursor = code_va
for start, end in covered + [(code_end, code_end)]:
    gap = cursor
    while gap < start:
        while gap < start and word(gap) == 0:
            gap += 4
        if gap >= start:
            break
        entries.add(gap)
        # Continue past this chunk: next function in the gap starts after a JR $ra + delay slot.
        while gap < start and word(gap) != 0x03E00008:
            gap += 4
        gap += 8
    cursor = max(cursor, end)

entries = sorted(e for e in entries if e not in registered and e != code_va)
for e in entries:
    print(f'  "sub_{e:08X}@0x{e:08X}",')
print(f"# {len(entries)} missing entries", file=sys.stderr)
