import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('mio_docker_build', Path(__file__).with_name('build.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LinkageTests(unittest.TestCase):
    def test_reject_dynamic_loader_and_other_architectures(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / 'mio'
            data = bytearray(120)
            data[:6] = b'\x7fELF\x02\x01'
            struct.pack_into('<H', data, 18, 62)
            struct.pack_into('<Q', data, 32, 64)
            struct.pack_into('<HH', data, 54, 56, 1)
            struct.pack_into('<I', data, 64, 1)
            image.write_bytes(data)
            self.assertEqual(module.require_static_amd64(image)['dynamic_dependencies'], [])
            for kind in (2, 3):
                struct.pack_into('<I', data, 64, kind); image.write_bytes(data)
                with self.assertRaises(ValueError): module.require_static_amd64(image)
            struct.pack_into('<I', data, 64, 1)
            struct.pack_into('<H', data, 18, 183); image.write_bytes(data)
            with self.assertRaises(ValueError): module.require_static_amd64(image)
