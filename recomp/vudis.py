"""Minimal VU micro-mode disassembler: python vudis.py <code.bin> <start byte addr hex> [count]."""
import struct
import sys

XYZW = "xyzw"


def dest(i):
    d = (i >> 21) & 0xF
    return "".join(c for c, bit in zip(XYZW, (8, 4, 2, 1)) if d & bit)


def upper(i):
    flags = "".join(f for f, b in (("I", 31), ("E", 30), ("M", 29), ("D", 28), ("T", 27)) if i >> b & 1)
    op = i & 0x3F
    ft, fs, fd, bc = (i >> 16) & 31, (i >> 11) & 31, (i >> 6) & 31, XYZW[i & 3]
    d = dest(i)
    names = {0x00: "add", 0x04: "sub", 0x08: "madd", 0x0C: "msub", 0x10: "max", 0x14: "mini", 0x18: "mul"}
    if op < 0x1C:
        base = names[op & ~3]
        text = f"{base}{bc}.{d} vf{fd}, vf{fs}, vf{ft}{bc}"
    elif op < 0x30:
        table = {0x1C: "mulq", 0x1D: "maxi", 0x1E: "muli", 0x1F: "minii", 0x20: "addq", 0x21: "maddq", 0x22: "addi",
                 0x23: "maddi", 0x24: "subq", 0x25: "msubq", 0x26: "subi", 0x27: "msubi"}
        if op in table:
            text = f"{table[op]}.{d} vf{fd}, vf{fs}"
        else:
            table2 = {0x28: "add", 0x29: "madd", 0x2A: "mul", 0x2B: "max", 0x2C: "sub", 0x2D: "msub", 0x2E: "opmsub",
                      0x2F: "mini"}
            text = f"{table2[op]}.{d} vf{fd}, vf{fs}, vf{ft}"
    elif op >= 0x3C:
        sop = (i & 3) | ((i >> 4) & 0x7C)
        accbc = {0x00: "adda", 0x04: "suba", 0x08: "madda", 0x0C: "msuba", 0x18: "mula"}
        if (sop & ~3) in accbc and sop < 0x1C:
            text = f"{accbc[sop & ~3]}{XYZW[sop & 3]}.{d} acc, vf{fs}, vf{ft}{XYZW[sop & 3]}"
        elif 0x10 <= sop <= 0x17:
            kind = "itof" if sop < 0x14 else "ftoi"
            text = f"{kind}{(0, 4, 12, 15)[sop & 3]}.{d} vf{ft}, vf{fs}"
        else:
            table = {0x1C: "mulaq", 0x1D: "abs", 0x1E: "mulai", 0x1F: "clip", 0x20: "addaq", 0x21: "maddaq",
                     0x22: "addai", 0x23: "maddai", 0x24: "subaq", 0x25: "msubaq", 0x26: "subai", 0x27: "msubai",
                     0x28: "adda", 0x29: "madda", 0x2A: "mula", 0x2C: "suba", 0x2D: "msuba", 0x2E: "opmula",
                     0x2F: "nop", 0x30: "nop"}
            name = table.get(sop, f"?uspecial{sop:x}")
            if name == "nop":
                text = "nop"
            elif name == "abs":
                text = f"abs.{d} vf{ft}, vf{fs}"
            elif name == "clip":
                text = f"clipw.xyz vf{fs}, vf{ft}w"
            else:
                text = f"{name}.{d} acc, vf{fs}, vf{ft}"
    else:
        text = f"?upper{op:x}"
    return (flags + " " if flags else "") + text


def lower(i, pc):
    if i in (0, 0x8000033C):
        return "nop"
    op = (i >> 25) & 0x7F
    it, is_, id_ = (i >> 16) & 15, (i >> 11) & 15, (i >> 6) & 15
    ft, fs = (i >> 16) & 31, (i >> 11) & 31
    imm11 = i & 0x7FF
    if imm11 & 0x400:
        imm11 -= 0x800
    imm15 = (i & 0x7FF) | (((i >> 21) & 0xF) << 11)
    d = dest(i)
    tgt = lambda: f"0x{(pc + 8 + imm11 * 8) & 0x3FFF:04x}"
    simple = {
        0x00: lambda: f"lq.{d} vf{ft}, {imm11}(vi{is_})",
        0x01: lambda: f"sq.{d} vf{fs}, {imm11}(vi{it})",
        0x04: lambda: f"ilw.{d} vi{it}, {imm11}(vi{is_})",
        0x05: lambda: f"isw.{d} vi{it}, {imm11}(vi{is_})",
        0x08: lambda: f"iaddiu vi{it}, vi{is_}, {imm15}",
        0x09: lambda: f"isubiu vi{it}, vi{is_}, {imm15}",
        0x10: lambda: f"fceq vi1, 0x{i & 0xFFFFFF:x}",
        0x11: lambda: f"fcset 0x{i & 0xFFFFFF:x}",
        0x12: lambda: f"fcand vi1, 0x{i & 0xFFFFFF:x}",
        0x13: lambda: f"fcor vi1, 0x{i & 0xFFFFFF:x}",
        0x14: lambda: f"fseq vi{it}",
        0x15: lambda: "fsset",
        0x16: lambda: f"fsand vi{it}, 0x{((i >> 21) & 1) << 11 | (i & 0x7FF):x}",
        0x17: lambda: f"fsor vi{it}",
        0x18: lambda: f"fmeq vi{it}, vi{is_}",
        0x1A: lambda: f"fmand vi{it}, vi{is_}",
        0x1B: lambda: f"fmor vi{it}, vi{is_}",
        0x1C: lambda: f"fcget vi{it}",
        0x20: lambda: f"b {tgt()}",
        0x21: lambda: f"bal vi{it}, {tgt()}",
        0x24: lambda: f"jr vi{is_}",
        0x25: lambda: f"jalr vi{it}, vi{is_}",
        0x28: lambda: f"ibeq vi{it}, vi{is_}, {tgt()}",
        0x29: lambda: f"ibne vi{it}, vi{is_}, {tgt()}",
        0x2C: lambda: f"ibltz vi{is_}, {tgt()}",
        0x2D: lambda: f"ibgtz vi{is_}, {tgt()}",
        0x2E: lambda: f"iblez vi{is_}, {tgt()}",
        0x2F: lambda: f"ibgez vi{is_}, {tgt()}",
    }
    if op in simple:
        return simple[op]()
    if op != 0x40:
        return f"?lower{op:x}"
    funct = i & 0x3F
    if funct == 0x30:
        return f"iadd vi{id_}, vi{is_}, vi{it}"
    if funct == 0x31:
        return f"isub vi{id_}, vi{is_}, vi{it}"
    if funct == 0x32:
        imm5 = (i >> 6) & 0x1F
        imm5 = imm5 - 32 if imm5 & 0x10 else imm5
        return f"iaddi vi{it}, vi{is_}, {imm5}"
    if funct == 0x34:
        return f"iand vi{id_}, vi{is_}, vi{it}"
    if funct == 0x35:
        return f"ior vi{id_}, vi{is_}, vi{it}"
    if funct < 0x3C:
        return f"?lower1-{funct:x}"
    f2 = (i & 3) | ((i >> 4) & 0x7C)
    fsf, ftf = XYZW[(i >> 21) & 3], XYZW[(i >> 23) & 3]
    table = {
        0x30: f"move.{d} vf{ft}, vf{fs}", 0x31: f"mr32.{d} vf{ft}, vf{fs}",
        0x34: f"lqi.{d} vf{ft}, (vi{is_}++)", 0x35: f"sqi.{d} vf{fs}, (vi{it}++)",
        0x36: f"lqd.{d} vf{ft}, (--vi{is_})", 0x37: f"sqd.{d} vf{fs}, (--vi{it})",
        0x38: f"div q, vf{fs}{fsf}, vf{ft}{ftf}", 0x39: f"sqrt q, vf{ft}{ftf}", 0x3A: f"rsqrt q, vf{fs}{fsf}, vf{ft}{ftf}",
        0x3B: "waitq", 0x3C: f"mtir vi{it}, vf{fs}{fsf}", 0x3D: f"mfir.{d} vf{ft}, vi{is_}",
        0x3E: f"ilwr.{d} vi{it}, (vi{is_})", 0x3F: f"iswr.{d} vi{it}, (vi{is_})",
        0x40: f"rnext.{d} vf{ft}, r", 0x41: f"rget.{d} vf{ft}, r", 0x42: f"rinit r, vf{fs}{fsf}",
        0x43: f"rxor r, vf{fs}{fsf}", 0x64: f"mfp.{d} vf{ft}, p", 0x68: f"xtop vi{it}", 0x69: f"xitop vi{it}",
        0x6C: f"xgkick vi{is_}", 0x70: f"esadd p, vf{fs}", 0x71: f"ersadd p, vf{fs}", 0x72: f"eleng p, vf{fs}",
        0x73: f"erleng p, vf{fs}", 0x74: f"eatanxy p, vf{fs}", 0x75: f"eatanxz p, vf{fs}", 0x76: f"esum p, vf{fs}",
        0x77: f"ersqrt p, vf{fs}{fsf}", 0x78: f"esqrt p, vf{fs}{fsf}", 0x79: f"esin p, vf{fs}{fsf}",
        0x7A: f"ercpr p, vf{fs}{fsf}", 0x7B: "waitp", 0x7C: f"eatan p, vf{fs}{fsf}", 0x7D: f"eexp p, vf{fs}{fsf}",
    }
    return table.get(f2, f"?lower2-{f2:x}")


def main():
    code = open(sys.argv[1], "rb").read()
    start = int(sys.argv[2], 16)
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    for pc in range(start, min(len(code), start + count * 8), 8):
        lo, up = struct.unpack_from("<II", code, pc)
        if up >> 31 & 1:
            low_text = f"loi 0x{lo:08x} ({struct.unpack('<f', struct.pack('<I', lo))[0]:g})"
        else:
            low_text = lower(lo, pc)
        print(f"{pc:04x}: {upper(up):42s} | {low_text}")


if __name__ == "__main__":
    main()
