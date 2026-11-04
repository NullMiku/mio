#!/usr/bin/env python3
"""Negative contract tests; no Go or target-native runtime required."""
import importlib.util
import json
import os
import io
import shutil
import tarfile
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("ci_runner", HERE / "runner.py")
verify = load("ci_verify", HERE / "verify.py")
isolation = load("release_isolation", HERE / "release_isolation.py")


class ContractTests(unittest.TestCase):
    def command(self, source, timeout=5):
        return runner.execute([sys.executable, "-c", source], timeout)

    def test_success(self):
        self.assertEqual(self.command("print('ok')")[3], "PASS")

    def test_false_assertion(self):
        self.assertEqual(self.command("assert 1 == 2")[3], "FAIL")

    def test_output_mismatch(self):
        result = subprocess.CompletedProcess([], 0, b"wrong\n", b"")
        with self.assertRaises(RuntimeError):
            verify.require_output(result, b"expected\n")

    def test_abnormal_exit(self):
        self.assertEqual(self.command("import os; os._exit(17)")[0], 17)

    def test_missing_tool(self):
        result = runner.execute(["mio-ci-nonexistent-tool-82ac"], 1)
        self.assertEqual((result[0], result[3]), (2, "NOT_RUN"))

    def test_timeout(self):
        result = self.command("import time; time.sleep(10)", 0.05)
        self.assertEqual((result[3], result[4]), ("FAIL", "timeout"))

    def test_empty_go_report(self):
        self.assertEqual(runner.assess("go", 0, b"", "PASS", "")[0], "NOT_RUN")

    def test_skipped_go_report(self):
        event = dict(Package="p", Test="TestSkipped", Action="skip")
        self.assertEqual(runner.assess("go", 0, json.dumps(event).encode(), "PASS", "")[0], "NOT_RUN")

    def test_empty_mio_report(self):
        data = dict(packages=[], summary=dict(passed=0, failed=0))
        self.assertEqual(runner.assess("mio", 0, json.dumps(data).encode(), "PASS", "")[0], "NOT_RUN")

    def test_failed_go_package_cannot_be_hidden(self):
        events = [dict(Package="p", Test="TestOK", Action="pass"), dict(Package="p", Action="fail")]
        self.assertEqual(runner.assess("go", 0, b"\n".join(json.dumps(e).encode() for e in events), "PASS", "")[0], "FAIL")

    def test_missing_native_seed_records_both_layers(self):
        host = runner.TARGETS["macos-arm64"]
        modules = {"fake": dict(module="fake", targets=["macos-arm64"], suites=["quick"], script="fake.sh", required_checks=["native", "independent"])}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, MIO_CI_RESULTS=directory, MIO_NATIVE_SEED=""), \
             patch.object(runner, "discover", return_value=modules), \
             patch.object(runner.platform, "system", return_value=host[0]), \
             patch.object(runner.platform, "machine", return_value=host[1]), \
             patch.object(runner.shutil, "which", return_value="fake-tool"):
            self.assertEqual(runner.run(["macos-arm64", "fake", "quick"]), 2)
            report = json.loads(next(Path(directory).glob("*/report.json")).read_text())
            self.assertEqual([r["status"] for r in report["checks"][0]["checks"]], ["NOT_RUN", "NOT_RUN"])

    def test_lying_framework(self):
        # A framework's zero exit code cannot override independently wrong output.
        with self.assertRaises(RuntimeError):
            verify.require_output(subprocess.CompletedProcess([], 0, b"2\n", b""), b"1\n")

    def test_bad_arguments_and_platform(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, MIO_CI_RESULTS=directory):
            self.assertEqual(runner.run([]), 2)
            self.assertEqual(runner.run(["windows-amd64", "core", "quick"]), 2)
            reports = list(Path(directory).glob("*/report.json"))
            self.assertEqual(len(reports), 2)
            self.assertTrue(all(json.loads(p.read_text())["status"] == "NOT_RUN" for p in reports))

    def test_aggregate_failure_and_empty_module(self):
        host = next(iter(runner.TARGETS.values()))
        for child_code, records, expected in ((1, [], 1), (0, [], 2),
                (0, [dict(name="failed-child", status="FAIL")], 1),
                (0, [dict(name="ok-child", status="PASS")], 0)):
            with self.subTest(child_code=child_code, records=records), tempfile.TemporaryDirectory() as directory:
                def fake_execute(argv, timeout, env=None):
                    if env and "MIO_CI_CHECKS" in env:
                        Path(env["MIO_CI_CHECKS"]).write_text("".join(json.dumps(r) + "\n" for r in records))
                        return child_code, b"", b"", "PASS" if child_code == 0 else "FAIL", "", 1
                    return 0, b"", b"", "PASS", "", 1
                modules = {"fake": dict(module="fake", engine="infrastructure", targets=["linux-amd64"], suites=["quick"], script="fake.sh")}
                with patch.dict(os.environ, MIO_CI_RESULTS=directory), patch.object(runner, "discover", return_value=modules), \
                     patch.object(runner.platform, "system", return_value=host[0]), \
                     patch.object(runner.platform, "machine", return_value=host[1]), \
                     patch.object(runner.shutil, "which", return_value="fake-tool"), \
                     patch.object(runner, "execute", side_effect=fake_execute):
                    self.assertEqual(runner.run(["linux-amd64", "fake", "quick"]), expected)

    def test_unsupported_module_suite_and_missing_dependency(self):
        host = runner.TARGETS["linux-amd64"]
        modules = {"fake": dict(module="fake", engine="infrastructure", targets=["linux-amd64"], suites=["quick"], script="fake.sh")}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, MIO_CI_RESULTS=directory), \
             patch.object(runner, "discover", return_value=modules), \
             patch.object(runner.platform, "system", return_value=host[0]), \
             patch.object(runner.platform, "machine", return_value=host[1]):
            self.assertEqual(runner.run(["linux-amd64", "fake", "impossible"]), 2)
            with patch.object(runner.shutil, "which", return_value=None):
                self.assertEqual(runner.run(["linux-amd64", "fake", "quick"]), 2)

    def test_packaging_rejects_test_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "polluted.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                for name in ("mio", "LICENSE", "README.txt", "runner.py"):
                    info = tarfile.TarInfo(name)
                    info.size = 4
                    archive.addfile(info, io.BytesIO(b"fake"))
            with self.assertRaisesRegex(RuntimeError, "unexpected or duplicate"):
                isolation.archive_audit(path)

    @unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "Bash/Git unavailable")
    def test_real_dispatch_and_logging(self):
        host = runner.TARGETS["linux-amd64"]
        for source, expected in (("print('executed')", 0), ("assert False", 1), (None, 2)):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                script = Path(directory) / "test.sh"
                body = '#!/usr/bin/env bash\nset -euo pipefail\n'
                if source is not None:
                    body += '"$PYTHON" "$TEST_CI_RUNNER" check command independent "$PYTHON" -c ' + "'" + source.replace("'", '"') + "'\n"
                script.write_text(body, encoding="utf-8")
                modules = {"fake": dict(module="fake", engine="infrastructure", targets=["linux-amd64"], suites=["quick"], script=str(script))}
                with patch.dict(os.environ, MIO_CI_RESULTS=directory, TEST_CI_RUNNER=str(HERE / "runner.py")), \
                     patch.object(runner, "discover", return_value=modules), \
                     patch.object(runner.platform, "system", return_value=host[0]), \
                     patch.object(runner.platform, "machine", return_value=host[1]):
                    self.assertEqual(runner.run(["linux-amd64", "fake", "quick"]), expected)
                report_path = next(Path(directory).glob("*/report.json"))
                report = json.loads(report_path.read_text())
                self.assertEqual(report["status"], {0: "PASS", 1: "FAIL", 2: "NOT_RUN"}[expected])
                if source is not None:
                    record = report["checks"][0]["checks"][0]
                    self.assertEqual(record["exit_code"], expected)
                    self.assertTrue(all(Path(p).exists() for p in record["artifacts"]))

    @unittest.skipUnless(shutil.which("bash"), "Bash unavailable; POSIX pipeline NOT_RUN")
    def test_pipefail(self):
        result = runner.execute(["bash", "-c", "set -euo pipefail; (exit 7) | tee /dev/null"], 5)
        self.assertEqual(result[0], 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
