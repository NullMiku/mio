#!/usr/bin/env python3
"""Independent PE reader/oracle. Consumes Mio output; never creates PE files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import tempfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Image:
    def __init__(self, data):
        self.data = data
        require(len(data) >= 64 and data[:2] == b"MZ", "DOS signature")
        pe = self.number(60, "I")
        require(pe % 8 == 0 and pe >= 64, "PE header alignment")
        require(self.take(pe, 4) == b"PE\0\0", "PE signature")
        machine, count, timestamp, symbols, symbol_count, optional_size, self.flags = struct.unpack(
            "<HHIIIHH", self.take(pe + 4, 20))
        require(machine == 0x8664 and 0 < count <= 8, "AMD64 section count")
        require((timestamp, symbols, symbol_count, optional_size) == (0, 0, 0, 240), "COFF fields")
        optional = pe + 24
        require(self.number(optional, "H") == 0x20B, "PE32+ magic")
        self.entry = self.number(optional + 16, "I")
        self.base = self.number(optional + 24, "Q")
        self.image_size = self.number(optional + 56, "I")
        headers = self.number(optional + 60, "I")
        self.dll_flags = self.number(optional + 70, "H")
        require(self.base == 0x140000000, "image base")
        require(self.number(optional + 32, "I") == 4096 and self.number(optional + 36, "I") == 512, "alignments")
        require(self.image_size % 4096 == 0 and headers % 512 == 0, "aligned sizes")
        require(self.number(optional + 68, "H") == 3 and self.dll_flags & 0x100, "console/NX")
        require(self.number(optional + 108, "I") == 16, "data directory count")
        self.directories = [struct.unpack("<II", self.take(optional + 112 + n * 8, 8)) for n in range(16)]
        table = optional + optional_size
        require(headers == ((table + count * 40 + 511) // 512) * 512, "header extent")
        self.sections = {}
        file_end, image_end = headers, 4096
        code_size, initialized_size, uninitialized_size = 0, 0, 0
        for n in range(count):
            name, virtual_size, rva, raw_size, offset, relocs, lines, nr, nl, flags = struct.unpack(
                "<8sIIIIIIHHI", self.take(table + n * 40, 40))
            name = name.rstrip(b"\0").decode("ascii")
            require(name and name not in self.sections, "unique section name")
            require(rva == image_end and virtual_size > 0 and raw_size % 512 == 0, "section layout")
            require((relocs, lines, nr, nl) == (0, 0, 0, 0), "image section reserved fields")
            require(flags & 0x40000000 and not (flags & 0x80000000 and flags & 0x20000000), "readable/W^X sections")
            if raw_size:
                require(offset == file_end, "contiguous raw sections")
                self.take(offset, raw_size)
                file_end += raw_size
            else:
                require(offset == 0, "BSS has no raw address")
            self.sections[name] = dict(rva=rva, size=virtual_size, raw_size=raw_size, offset=offset, flags=flags)
            image_end = ((rva + virtual_size + 4095) // 4096) * 4096
            if name == ".text":
                code_size += raw_size
            else:
                initialized_size += raw_size
            uninitialized_size += max(0, virtual_size - raw_size)
        require(len(data) == file_end and self.image_size == image_end, "file/image ends")
        require(tuple(self.number(optional + at, "I") for at in (4, 8, 12)) ==
                (code_size, initialized_size, uninitialized_size), "optional section size totals")
        require(self.number(optional + 20, "I") == self.sections[".text"]["rva"], "BaseOfCode")
        require(self.sections[".text"]["flags"] == 0x60000020, "text RX code flags")
        self.at_rva(self.entry, 1, ".text")
        for n, (rva, size) in enumerate(self.directories):
            require((rva == 0) == (size == 0), "directory pair")
            if rva:
                require(n in (1, 3, 5, 12), "unsupported directory unexpectedly emitted")
                self.at_rva(rva, size)
        self.imports, self.iat_slots = self.read_imports()
        self.unwind = self.read_unwind()
        self.relocations = self.read_relocations()

    def take(self, at, size):
        require(0 <= at <= len(self.data) and 0 <= size <= len(self.data) - at, "file read bounds")
        return self.data[at:at + size]

    def number(self, at, fmt):
        return struct.unpack("<" + fmt, self.take(at, struct.calcsize("<" + fmt)))[0]

    def at_rva(self, rva, size, name=None):
        for key, s in self.sections.items():
            if s["rva"] <= rva and size <= s["size"] - (rva - s["rva"]):
                require(name is None or key == name, "RVA section ownership")
                delta = rva - s["rva"]
                require(size <= s["raw_size"] - delta, "RVA backed by file bytes")
                return s["offset"] + delta
        raise ValueError("RVA outside sections")

    def string(self, rva):
        result = bytearray()
        for i in range(256):
            byte = self.data[self.at_rva(rva + i, 1)]
            if byte == 0:
                require(result, "nonempty import name")
                return result.decode("ascii")
            require(33 <= byte <= 126, "printable ASCII import")
            result.append(byte)
        raise ValueError("unterminated import name")

    def read_imports(self):
        rva, size = self.directories[1]
        if not rva:
            require(self.directories[12] == (0, 0), "IAT without imports")
            return [], []
        require(size % 20 == 0 and size >= 40, "import descriptor extent")
        result, slots = [], []
        iat_rva, iat_size = self.directories[12]
        cursor = iat_rva
        for n in range(size // 20):
            descriptor = struct.unpack("<5I", self.take(self.at_rva(rva + n * 20, 20), 20))
            if n == size // 20 - 1:
                require(descriptor == (0, 0, 0, 0, 0), "null import descriptor")
                break
            lookup, timestamp, chain, library, iat = descriptor
            require(timestamp == chain == 0 and iat == cursor and lookup % 8 == iat % 8 == 0, "ILT/IAT layout")
            symbols = []
            for i in range(4097):
                thunk = self.number(self.at_rva(lookup + i * 8, 8), "Q")
                require(thunk == self.number(self.at_rva(iat + i * 8, 8), "Q"), "initial IAT equals ILT")
                if thunk == 0:
                    break
                require(thunk < 2**32 and thunk % 2 == 0, "named hint RVA")
                require(self.number(self.at_rva(thunk, 2), "H") == 0, "zero import hint")
                symbols.append(self.string(thunk + 2))
                slots.append(iat + i * 8)
            else:
                raise ValueError("unterminated ILT")
            require(symbols, "nonempty DLL imports")
            result.append((self.string(library), symbols))
            cursor = iat + (len(symbols) + 1) * 8
        require(cursor - iat_rva == iat_size, "IAT directory covers null entries")
        return result, slots

    def read_unwind(self):
        rva, size = self.directories[3]
        require(size % 12 == 0, "RUNTIME_FUNCTION extent")
        previous, result = 0, []
        for n in range(size // 12):
            begin, end, info = struct.unpack("<III", self.take(self.at_rva(rva + n * 12, 12, ".pdata"), 12))
            require(previous <= begin < end and info % 4 == 0, "sorted function range/unwind alignment")
            self.at_rva(begin, end - begin, ".text")
            at = self.at_rva(info, 4, ".xdata")
            version, prolog, count, frame = self.take(at, 4)
            require(version == 1 and frame == 0 and prolog <= end - begin, "bounded UNWIND_INFO")
            stack = 0
            if count:
                codes = self.take(self.at_rva(info + 4, ((count + 1) // 2) * 4, ".xdata"), ((count + 1) // 2) * 4)
                offset, operation = codes[:2]
                require(0 < offset <= prolog, "unwind instruction end offset")
                if operation % 16 == 2:
                    require(count == 1 and codes[2:] == b"\0\0", "small allocation padding")
                    stack = (operation // 16 + 1) * 8
                else:
                    require(operation == 1 and count == 2, "large allocation form")
                    stack = struct.unpack_from("<H", codes, 2)[0] * 8
                    require(stack > 128, "canonical large allocation")
            result.append((begin, end, stack))
            previous = end
        return result

    def read_relocations(self):
        rva, size = self.directories[5]
        if not rva:
            require(self.flags & 1 and not self.dll_flags & 0x60, "fixed image flags")
            return []
        require(not self.flags & 1 and self.dll_flags & 0x60 == 0x60, "relocatable image flags")
        previous, cursor, result = -1, 0, []
        while cursor < size:
            at = self.at_rva(rva + cursor, 8, ".reloc")
            page, block_size = struct.unpack("<II", self.take(at, 8))
            require(page % 4096 == 0 and page > previous, "sorted relocation pages")
            require(block_size >= 12 and block_size % 4 == 0 and block_size <= size - cursor, "relocation block bounds")
            words = struct.unpack("<" + "H" * ((block_size - 8) // 2), self.take(at + 8, block_size - 8))
            for index, word in enumerate(words):
                if word == 0:
                    require(index == len(words) - 1, "ABSOLUTE final padding")
                    continue
                require(word >> 12 == 10, "AMD64 DIR64 relocation")
                target = page + (word & 0xFFF)
                require(not result or result[-1] < target, "unique sorted relocation sites")
                address = self.number(self.at_rva(target, 8), "Q")
                require(self.base <= address < self.base + self.image_size, "absolute target in image")
                result.append(target)
            previous, cursor = page, cursor + block_size
        require(cursor == size and result, "complete nonempty relocation directory")
        return result


def verify_console(directory, execute=False):
    if execute:
        require(platform.system() == "Windows" and platform.machine().lower() in ("amd64", "x86_64"), "execution requires real Windows AMD64")
    executions = []
    cases = (("encoded-exit47.exe", 47, b""),
             ("encoded-stdout48.exe", 48, b"Mio Windows AMD64\n"),
             ("encoded-binary49.exe", 49, b"Mio\0\xff\n"),
             ("encoded-empty50.exe", 50, b""))
    for name, code, output in cases:
        image = Image((directory / name).read_bytes())
        text = image.sections[".text"]
        at = image.at_rva(image.entry, text["size"])
        stack = 72 if output else 40
        require(image.take(at, 7) == b"\x48\x81\xec" + struct.pack("<I", stack), "encoded prolog/stack allocation")
        require(image.take(at + text["size"] - 8, 8) == b"\x48\x81\xc4" + struct.pack("<I", stack) + b"\xc3", "encoded epilog")
        require(image.unwind == [(image.entry, image.entry + text["size"], stack)], "encoded function unwind")
        info = image.sections[".xdata"]["offset"]
        require(image.take(info, 6) == bytes((1, 7, 1, 0, 7, 2 + (stack // 8 - 1) * 16)), "unwind matches seven-byte sub rsp")
        symbols = ["GetStdHandle", "WriteFile", "ExitProcess"] if output else ["ExitProcess"]
        require(image.imports == [("KERNEL32.dll", symbols)], "encoded API imports")
        # Each absolute operand must have a DIR64 record. IAT calls use the
        # shared encoder's mov r11,imm64; call [r11+disp32] sequence.
        expected = [image.base + slot for slot in image.iat_slots]
        if output:
            rdata = image.sections[".rdata"]
            require(rdata["size"] == len(output), "exact output payload extent")
            require(image.take(rdata["offset"], len(output)) == output, "exact binary output payload")
            expected.insert(1, image.base + rdata["rva"])
        actual = []
        for site in image.relocations:
            operand = image.at_rva(site, 8, ".text")
            value = image.number(operand, "Q")
            actual.append(value)
            if value in [image.base + slot for slot in image.iat_slots]:
                require(image.take(operand - 2, 2) == b"\x49\xbb" and
                        image.take(operand + 8, 7) == b"\x41\xff\x93\0\0\0\0", "encoded IAT call operand")
            else:
                require(image.take(operand - 2, 2) == b"\x48\xba", "encoded rdata address operand")
        require(actual == expected, "all IAT/data operands are relocated in code order")
        if execute:
            process = subprocess.run([str((directory / name).resolve())], capture_output=True, timeout=15,
                                     env=dict(os.environ, PATH=""))
            (directory / (name + ".stdout.log")).write_bytes(process.stdout)
            (directory / (name + ".stderr.log")).write_bytes(process.stderr)
            executions.append(dict(image=name, exit_code=process.returncode,
                                   stdout_hex=process.stdout.hex(), stderr_hex=process.stderr.hex(),
                                   image_sha256=hashlib.sha256(image.data).hexdigest()))
            require((process.returncode, process.stdout, process.stderr) == (code, output, b""), "encoded native exit/output: " + name)
    if execute:
        # A real inherited read-only stdout handle makes WriteFile fail. The
        # program must take its error exit, without silently claiming success.
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "read-only-stdout"
            path.write_bytes(b"unchanged")
            with path.open("rb") as readonly:
                process = subprocess.run([str((directory / "encoded-stdout48.exe").resolve())],
                                         stdout=readonly, stderr=subprocess.PIPE, timeout=15,
                                         env=dict(os.environ, PATH=""))
            require(process.returncode == 111 and process.stderr == b"" and path.read_bytes() == b"unchanged",
                    "WriteFile failure must produce exit 111")
            executions.append(dict(image="encoded-stdout48.exe", stdout_handle="read-only",
                                   exit_code=process.returncode, stderr_hex=process.stderr.hex()))
    return dict(console_structure="PASS", console_images=4,
                console_windows_execution="PASS" if execute else "NOT_RUN",
                console_executed_images=4 if execute else 0,
                console_write_failure="PASS" if execute else "NOT_RUN", console_executions=executions)


def verify(directory, execute=False):
    images = {name: Image((directory / name).read_bytes()) for name in (
        "exit42.exe", "relocated43.exe", "bss44.exe", "paged45.exe", "leaf.exe", "large-unwind.exe")}
    for name, code in (("exit42.exe", 42), ("paged45.exe", 45)):
        image = images[name]
        at = image.at_rva(image.entry, 16)
        require(image.take(at, 11) == bytes((0x48, 0x83, 0xEC, 40, 0xB9, code, 0, 0, 0, 0xFF, 0x15)), "exit fixture instructions")
        target = image.entry + 15 + image.number(at + 11, "i")
        require(target == image.iat_slots[0], "RIP-relative call reaches ExitProcess IAT")
        require(image.unwind == [(image.entry, image.entry + 16, 40)], "exit fixture unwind")
    bss = images["bss44.exe"]
    at = bss.at_rva(bss.entry, 20)
    require(bss.take(at, 6) == b"\x48\x83\xec\x28\x8b\x0d" and bss.take(at + 10, 5) == b"\x83\xc1\x2c\xff\x15", "BSS load/exit instructions")
    require(bss.entry + 10 + bss.number(at + 6, "i") == bss.sections[".data"]["rva"] + 4093, "load at end of virtual BSS")
    require(bss.entry + 19 + bss.number(at + 15, "i") == bss.iat_slots[0], "BSS exit IAT call")
    require(bss.unwind == [(bss.entry, bss.entry + 20, 40)], "BSS unwind record")
    relocated = images["relocated43.exe"]
    at = relocated.at_rva(relocated.entry, 22)
    require(relocated.number(at + 11, "Q") == relocated.base + relocated.iat_slots[0], "absolute IAT patch")
    require(relocated.relocations == [relocated.entry + 11] and len(relocated.sections) == 7, "DIR64 fixture and expanded header")
    require(images["exit42.exe"].imports == [("KERNEL32.dll", ["ExitProcess"])], "single import fixture")
    require(images["bss44.exe"].imports == [("KERNEL32.dll", ["ExitProcess", "GetStdHandle"]), ("USER32.dll", ["MessageBoxA"])], "multiple DLL fixture")
    require(images["bss44.exe"].sections[".data"]["raw_size"] == 0 and images["bss44.exe"].sections[".data"]["size"] == 4097, "pure BSS fixture")
    text = images["paged45.exe"].sections[".text"]["rva"]
    require(images["paged45.exe"].relocations == [text + 24, text + 32, text + 4096, text + 8192], "multiple relocation pages")
    require(images["large-unwind.exe"].unwind == [(4096, 4111, 136)], "large unwind fixture")
    require(not images["leaf.exe"].imports and not images["leaf.exe"].unwind, "empty optional directories")

    # Prove the independent oracle rejects deliberate structural corruption.
    original = images["exit42.exe"].data
    mutations = [(0, b"NO"), (60, struct.pack("<I", len(original))),
                 (132, b"\0\0"), (168, struct.pack("<I", 0xFFFFFFFF)),
                 (188, struct.pack("<I", 1)), (272, struct.pack("<I", 0xFFFFFFFF)),
                 (412, struct.pack("<I", 1))]
    for offset, value in mutations:
        damaged = bytearray(original)
        damaged[offset:offset + len(value)] = value
        try:
            Image(bytes(damaged))
        except ValueError:
            continue
        raise ValueError("oracle accepted mutation at " + str(offset))
    results = dict(structure="PASS", images=len(images), rejected_mutations=len(mutations), windows_execution="NOT_RUN")
    if execute:
        require(platform.system() == "Windows" and platform.machine().lower() in ("amd64", "x86_64"), "execution requires real Windows AMD64")
        for name, code in (("exit42.exe", 42), ("relocated43.exe", 43), ("bss44.exe", 44), ("paged45.exe", 45)):
            process = subprocess.run([str((directory / name).resolve())], capture_output=True, timeout=15,
                                     env=dict(os.environ, PATH=""))
            require((process.returncode, process.stdout, process.stderr) == (code, b"", b""), "native exit/output: " + name)
        results.update(windows_execution="PASS", executed_images=4)
    try:
        results.update(verify_console(directory, execute=execute))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        error.layer = "console_windows_execution" if execute else "console_structure"
        raise
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path("build/pe-writer"))
    parser.add_argument("--execute", action="store_true")
    options = parser.parse_args()
    print(json.dumps(verify(options.directory, options.execute), sort_keys=True))
