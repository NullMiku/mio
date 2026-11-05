"""Development-only negative checks for the PE evidence driver."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import run as driver


def passed_report():
    return dict(summary=dict(status="passed", passed=1, failed=0),
                packages=[dict(status="passed", tests=[dict(status="passed")])])


class DriverTests(unittest.TestCase):
    def test_complete_report(self):
        self.assertEqual(driver.reference_test_count(passed_report()), 1)

    def test_mixed_skip_is_not_run(self):
        data = passed_report()
        data["packages"][0]["tests"].append(dict(status="skipped"))
        with self.assertRaises(driver.NotRunError):
            driver.reference_test_count(data)

    def test_empty_tests_are_not_run(self):
        data = passed_report()
        data["packages"][0]["tests"] = []
        data["summary"]["passed"] = 0
        with self.assertRaises(driver.NotRunError):
            driver.reference_test_count(data)

    def test_skip_does_not_hide_failure(self):
        data = passed_report()
        data["packages"][0]["tests"].extend([dict(status="failed"), dict(status="skipped")])
        data["summary"]["failed"] = 1
        with self.assertRaises(ValueError) as caught:
            driver.reference_test_count(data)
        self.assertNotIsInstance(caught.exception, driver.NotRunError)

    def test_inconsistent_or_failed_report_is_rejected(self):
        for change in ("count", "package", "test", "summary"):
            data = copy.deepcopy(passed_report())
            if change == "count":
                data["summary"]["passed"] = 2
            elif change == "package":
                data["packages"][0]["status"] = "compile_failed"
            elif change == "test":
                data["packages"][0]["tests"][0]["status"] = "failed"
            else:
                data["summary"]["failed"] = 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                driver.reference_test_count(data)

    def test_missing_compiler_replaces_old_success(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = output / "report.json"
            report.write_text('{"generation":"PASS"}', encoding="utf-8")
            args = ["run.py", "--mio", str(output / "missing.exe"),
                    "--mode", "reference", "--output", str(output)]
            with patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()), \
                    self.assertRaises(OSError):
                driver.main()
            result = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(result["setup"], "FAIL")
            for layer in ("generation", "structure", "windows_execution", "reference_tests", "mio_native_tests"):
                self.assertEqual(result[layer], "NOT_RUN")

    def test_skip_stops_generation_and_records_not_run(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            compiler = output / "compiler.exe"
            compiler.write_bytes(b"test double; never executed")
            data = passed_report()
            data["packages"][0]["tests"].append(dict(status="skipped"))
            process = subprocess.CompletedProcess([], 0, json.dumps(data).encode(), b"")
            args = ["run.py", "--mio", str(compiler), "--mode", "reference", "--output", str(output)]
            with patch.object(sys, "argv", args), patch.object(driver.subprocess, "run", return_value=process) as run, \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaises(driver.NotRunError):
                driver.main()
            self.assertEqual(run.call_count, 1)
            result = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(result["reference_tests"], "NOT_RUN")
            self.assertEqual(result["generation"], "NOT_RUN")

    def test_native_build_cannot_reuse_stale_builder(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            compiler = output / "compiler.exe"
            compiler.write_bytes(b"test double; never executed")
            builder = output / "builder.native"
            builder.write_bytes(b"stale builder")
            args = ["run.py", "--mio", str(compiler), "--mode", "native", "--output", str(output)]

            def execute(command, **kwargs):
                if command[0] == str(compiler):
                    return subprocess.CompletedProcess(command, 0, b"", b"")
                self.assertFalse(builder.exists(), "stale native builder survived cleanup")
                raise FileNotFoundError("compiler produced no builder")

            with patch.object(sys, "argv", args), patch.object(driver.subprocess, "run", side_effect=execute), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaises(FileNotFoundError):
                driver.main()
            result = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(result["generation"], "FAIL")
            self.assertEqual(result["structure"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
