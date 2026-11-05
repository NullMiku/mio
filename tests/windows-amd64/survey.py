#!/usr/bin/env python3
"""Development-only: which Mochi opcodes and native operations does a Mio program REACH, and which does lowerwin lack?
Input: `mio disasm` output of the program's .mochi (built by the Go frontend). Output: markdown."""
import re
import sys
from collections import Counter
from pathlib import Path

NAMES = """Constant Add Pop Sub Mul Div Neg True False Not Equal NotEqual Less LessEqual Greater GreaterEqual Jump JumpIfFalse
SetGlobal GetGlobal Nil Chant SetLocal GetLocal Call Return ReturnValue IntToFloat FloatToInt Array Index Len SetIndex IsNil
SetNullableIndex Struct GetField Enum EnumTag GetEnumValue Map MapGet MapSet Function CallValue Closure GetUpvalue SetUpvalue
DefineLocal IntToFloat32 Float32ToInt Float32ToFloat64 Float64ToFloat32 Math IntegerConvert ArrayTyped ArrayMake
ArrayWithCapacity ArrayPush ArrayCapacity ArrayReserve ArrayClone ArrayTruncate ArrayAppendAll DataConvert""".split()
# Keep in sync with bunko/kiso/aot/lowerwin/lowerwin.mio supported().
SCALAR = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 23, 24, 25, 26, 27, 49}
# Keep in sync with bunko/kiso/aot/lowerwinrt/lowerwinrt.mio supported() (same opcode set as lowerlinux).
HEAP = set(range(1, 21)) | {22, 21} | set(range(23, 28)) | set(range(30, 41)) | {28, 29} | set(range(50, 54)) | {49} | set(range(44, 49)) | {66, 67} | {41, 42, 43} | {54, 55} | set(range(56, 66))
SUPPORTED = SCALAR


def parse(text):
    head, _, rest = text.partition("Functions (")
    main = re.findall(r"^\d{4} Op(\w+)(?: (\d+))?", head.split("Instructions:")[-1], re.M)
    funcs = {}
    current = None
    for line in rest.splitlines()[1:]:
        m = re.match(r"\s+Function (\d+) (\S+) params=(\d+)", line)
        if m:
            current = int(m.group(1))
            funcs[current] = dict(name=m.group(2), ops=[])
            continue
        m = re.match(r"^\d{4} Op(\w+)(?: (\d+))?", line)
        if m and current is not None:
            funcs[current]["ops"].append((m.group(1), int(m.group(2)) if m.group(2) else None))
    return main, funcs


def main():
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    title = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
    main_ops, funcs = parse(text)
    main_ops = [(a, int(b) if b else None) for a, b in main_ops]
    seen, todo = set(), [op for op in main_ops]
    work = list(main_ops)
    reach = set()
    stack = [o for o in main_ops]
    pending = []
    def visit(ops):
        for name, arg in ops:
            if name in ("Call", "Function", "Closure") and arg is not None and arg in funcs and arg not in reach:
                reach.add(arg)
                pending.append(arg)
    visit(main_ops)
    while pending:
        visit(funcs[pending.pop()]["ops"])
    hist = Counter(name for name, _ in main_ops)
    for f in reach:
        hist.update(name for name, _ in funcs[f]["ops"])
    natives = sorted("::".join(funcs[f]["name"].split("::")[1:3]) for f in reach if not funcs[f]["ops"])
    print("## %s\n" % title)
    print("Reachable functions: %d of %d. Reachable native (body-less) operations: %d.\n" % (len(reach), len(funcs), len(natives)))
    print("| opcode | uses | lowerwin (scalar) | lowerwinrt (heap) |\n|---|---:|---|---|")
    for name, n in sorted(hist.items(), key=lambda kv: -kv[1]):
        num = NAMES.index(name) + 1
        print("| %s (%d) | %d | %s | %s |" % (name, num, n, "supported" if num in SCALAR else "MISSING", "supported" if num in HEAP else "MISSING"))
    print("\nNative operations reached:\n")
    for n in natives:
        print("- `%s`" % n)
    for label, have in (("lowerwin (scalar)", SCALAR), ("lowerwinrt (heap)", HEAP)):
        missing = [n for n in hist if NAMES.index(n) + 1 not in have]
        print("\nMissing opcodes in %s: %s" % (label, ", ".join(sorted(missing)) or "none"))


if __name__ == "__main__":
    main()
