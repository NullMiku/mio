"""Reject corruption of actual Mio-generated console images; no image generation here."""
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest

from verify import Image, verify_console

IMAGES = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else Path("build/pe-writer").resolve()


class ConsoleOracleTests(unittest.TestCase):
    def check_mutation(self, field):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ("encoded-exit47.exe", "encoded-stdout48.exe", "encoded-binary49.exe", "encoded-empty50.exe"):
                shutil.copyfile(IMAGES / name, directory / name)
            target = directory / "encoded-stdout48.exe"
            data = bytearray(target.read_bytes())
            image = Image(data)
            if field == "payload":
                data[image.sections[".rdata"]["offset"]] ^= 1
            elif field == "stack":
                data[image.sections[".text"]["offset"] + 3] = 40
            elif field == "unwind":
                data[image.sections[".xdata"]["offset"] + 5] = 66
            elif field == "iat_call":
                data[image.at_rva(image.relocations[0], 8) + 9] = 0x90
            elif field == "relocations":
                at = image.sections[".reloc"]["offset"] + 8
                struct.pack_into("<H", data, at, 0)
            target.write_bytes(data)
            with self.assertRaises(ValueError):
                verify_console(directory)

    def test_output_corruption(self):
        self.check_mutation("payload")

    def test_stack_corruption(self):
        self.check_mutation("stack")

    def test_unwind_corruption(self):
        self.check_mutation("unwind")

    def test_iat_call_corruption(self):
        self.check_mutation("iat_call")

    def test_relocation_corruption(self):
        self.check_mutation("relocations")


if __name__ == "__main__":
    unittest.main()
