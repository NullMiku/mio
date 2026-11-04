#!/usr/bin/env python3
"""Independent check of the ELF64 images written by kiso/aot/elf (outside testing.expect).

A small Mio program, built with the compiler under test ($MIO_CI_MIO, `build`, the same way
scripts/ci/verify_native.py does) and executed, builds four images with elf.executable and writes them with
kiso/fs. This script then parses the files with Python's struct
module and compares every header, program header and section header field with values computed here
from the ELF specification and from the documented layout, not read back from the Mio code.

Images: bss and no bss, entry offset 0 and non-zero, and one whose code writes to and reads back the zero-filled
data segment.

Checks, in order of independence:
  1. struct-level parse of both images (always).
  2. GNU readelf, if one is available (readelf, greadelf): type, machine, entry, segments, sections.
     Reported as "readelf: NOT_RUN (...)" when absent; that is not a pass for that layer.
  3. Execution, only on a Linux x86-64 host: every image must exit with status 42 and print nothing. Reported as "execution: NOT_RUN (...)" on any other host.
Nothing is installed or modified. Exit status: 0 all executed checks passed, 1 a check failed.
Environment: MIO_CI_MIO (compiler), MIO_CI_MODULE_DIR (scratch directory).
"""
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
IMAGE_BASE, DATA_BASE, CODE_OFFSET = 0x400000, 0x10000000, 0x1000
# exit_group(42): mov edi,42 ; mov eax,231 ; syscall
EXIT_42 = bytes([0xBF, 0x2A, 0, 0, 0, 0xB8, 0xE7, 0, 0, 0, 0x0F, 0x05])
NOPS = bytes([0x90, 0x90, 0x90])
# Stores 42 into the zero-filled RW segment and exits with the byte read back (needs the data segment mapped):
# mov byte [0x10000000],42 ; movzx edi,byte [0x10000000] ; mov eax,231 ; syscall
DATA_42 = bytes([0xC6, 0x04, 0x25, 0, 0, 0, 0x10, 0x2A, 0x0F, 0xB6, 0x3C, 0x25, 0, 0, 0, 0x10, 0xB8, 0xE7, 0, 0, 0, 0x0F, 0x05])
# name, code, entry offset, bss size, expected exit status when executed
IMAGES = [
    ("bss-entry0", EXIT_42, 0, 4104, 42),
    ("nobss-entry3", NOPS + EXIT_42, 3, 0, 42),
    ("bss-entry3", NOPS + EXIT_42, 3, 4104, 42),
    ("bss-store", DATA_42, 0, 4104, 42),
]


def source(paths):
    def array(data):
        return "[" + ", ".join(f"uint8({b})" for b in data) + "]"
    out = 'yobu "kiso/aot/elf";\nyobu "kiso/fs";\nkaku ok = hai;\n'
    for i, (name, code, entry, bss, _) in enumerate(IMAGES):
        out += f"kaku i{i} = elf.executable(elf.ImageSpec {{ code: {array(code)}, entry_offset: {entry}, bss_size: {bss} }});\n"
        out += f"moshi (i{i}.error != \"\") {{ ok = iie; }}\n"
        out += f"kaku w{i} = fs.write_all({json.dumps(str(paths[name]))}, i{i}.bytes);\n"
    return out + "chant(ok);\n"


def align(value, boundary):
    return (value + boundary - 1) // boundary * boundary


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def check_image(data, code, entry_offset, bss_size):
    text_end = CODE_OFFSET + len(code)
    names = b"\0.text\0.bss\0.shstrtab\0"
    names_offset = align(text_end, 8)
    sections_offset = align(names_offset + len(names), 8)
    phnum = 3 if bss_size else 2
    expect(len(data) == sections_offset + 4 * 64, "file length")
    ident, etype, machine, version, entry, phoff, shoff, flags, ehsize, phentsize, phnum_f, shentsize, shnum, shstrndx = \
        struct.unpack_from("<16sHHIQQQIHHHHHH", data)
    expect(ident == b"\x7fELF\x02\x01\x01" + b"\0" * 9, "e_ident: ELF64, little endian, version 1, System V ABI")
    expect((etype, machine, version) == (2, 62, 1), "ET_EXEC, EM_X86_64, EV_CURRENT")
    expect(entry == IMAGE_BASE + CODE_OFFSET + entry_offset, "e_entry")
    expect((phoff, shoff, flags) == (64, sections_offset, 0), "e_phoff, e_shoff, e_flags")
    expect((ehsize, phentsize, phnum_f, shentsize, shnum, shstrndx) == (64, 56, phnum, 64, 4, 3), "header sizes and counts")
    phdrs = [struct.unpack_from("<IIQQQQQQ", data, 64 + 56 * i) for i in range(phnum)]
    expect(phdrs[0] == (1, 5, 0, IMAGE_BASE, IMAGE_BASE, text_end, text_end, 0x1000), "PT_LOAD R+X maps the file from offset 0")
    if bss_size:
        expect(phdrs[1] == (1, 6, 0, DATA_BASE, DATA_BASE, 0, bss_size, 0x1000), "PT_LOAD R+W zero-filled data")
    expect(phdrs[-1] == (0x6474E551, 6, 0, 0, 0, 0, 0, 16), "PT_GNU_STACK R+W without X")
    expect(data[CODE_OFFSET:text_end] == code, "code bytes at 0x1000")
    expect(all(b == 0 for b in data[64 + 56 * phnum:CODE_OFFSET]), "padding before the code is zero")
    expect(data[names_offset:names_offset + len(names)] == names, ".shstrtab contents")
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, sections_offset + 64 * i) for i in range(4)]
    expect(sections[0] == (0,) * 10, "null section")
    expect(sections[1] == (1, 1, 6, IMAGE_BASE + CODE_OFFSET, CODE_OFFSET, len(code), 0, 0, 16, 0), ".text: PROGBITS, AX")
    expect(sections[2] == (7, 8, 3, DATA_BASE, text_end, bss_size, 0, 0, 8, 0), ".bss: NOBITS, WA")
    expect(sections[3] == (12, 3, 0, 0, names_offset, len(names), 0, 0, 1, 0), ".shstrtab: STRTAB")


def readelf_tool():
    for name in ("readelf", "greadelf"):
        path = shutil.which(name)
        if path:
            first = subprocess.run([path, "--version"], capture_output=True, text=True).stdout.splitlines()[:1]
            if first and "GNU readelf" in first[0]:
                return path
    return None


def main():
    mio = os.environ["MIO_CI_MIO"]
    work = Path(os.environ["MIO_CI_MODULE_DIR"])
    paths = {name: work / ("elf-" + name + ".bin") for name, *_ in IMAGES}
    program = work / "elf-images.mio"
    program.write_text(source(paths), encoding="utf-8")
    native = work / "elf-images.native"
    build = subprocess.run([mio, "build", str(program), "--bunko-root", str(ROOT / "bunko"), "-o", str(native)],
                           capture_output=True, text=True, timeout=600)
    (work / "elf-images.build.log").write_text(build.stdout + build.stderr)
    if build.returncode != 0:
        raise RuntimeError(f"building the Mio image writer failed: exit={build.returncode} {build.stderr!r}")
    run = subprocess.run([str(native)], capture_output=True, text=True, timeout=120)
    (work / "elf-images.stdout.log").write_text(run.stdout)
    (work / "elf-images.stderr.log").write_text(run.stderr)
    if run.returncode != 0 or run.stdout != "hai\n":
        raise RuntimeError(f"the Mio image writer failed: exit={run.returncode} stdout={run.stdout!r} stderr={run.stderr!r}")
    for name, code, entry, bss, _ in IMAGES:
        check_image(paths[name].read_bytes(), code, entry, bss)
    print(f"struct parse: PASS ({len(IMAGES)} images, every header field compared)")

    readelf = readelf_tool()
    if readelf is None:
        print("readelf: NOT_RUN (no GNU readelf on PATH)")
    else:
        out = subprocess.run([readelf, "-h", "-l", "-S", "-W", str(paths["bss-entry0"])], capture_output=True, text=True, check=True).stdout
        for needle in ("Type:                              EXEC (Executable file)", "Advanced Micro Devices X86-64",
                       "Entry point address:               0x401000", "GNU_STACK", ".shstrtab"):
            expect(needle in out, "readelf output lacks " + repr(needle))
        print(f"readelf: PASS ({readelf})")

    if platform.system() == "Linux" and platform.machine() == "x86_64":
        for name, _, _, _, status in IMAGES:
            image = work / ("elf-run-" + name)
            shutil.copyfile(paths[name], image)
            os.chmod(image, 0o755)
            result = subprocess.run([str(image)], capture_output=True, timeout=30)
            expect((result.returncode, result.stdout, result.stderr) == (status, b"", b""), f"executing {name} gave {result!r}")
        print(f"execution: PASS ({len(IMAGES)} images exited with status 42 and printed nothing)")
    else:
        print(f"execution: NOT_RUN (host is {platform.system()} {platform.machine()}, not Linux x86_64)")
    print("elf independent oracle PASS")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError) as error:
        print("elf independent oracle FAIL: " + str(error), file=sys.stderr)
        sys.exit(1)
