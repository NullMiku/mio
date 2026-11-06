import copy
import io
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
import zipfile

from package import digest, extract, gate, inventory, package
from prepare import prepare, EMPTY


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def report(self):
        import os
        self.compiler = self.root / 'mio'
        self.compiler.write_bytes(b'fixed point native compiler')
        sha = digest(self.compiler)
        self.inputs = dict(source_sha='a'*40, embedded_bunko=False)
        return dict(target='linux-amd64', status='PASS', source_sha='a'*40,
                    run=dict(id=os.getenv('GITHUB_RUN_ID', ''), attempt=os.getenv('GITHUB_RUN_ATTEMPT', '')),
                    checks=[dict(name='cli-fixed-point', status='PASS', engine='native', required=True)],
                    hashes={f'cli-{s}': sha for s in 'BCD'})

    def test_gate_rejects_failed_unrun_foreign_or_wrong_compiler(self):
        report = self.report()
        gate(report, self.compiler, self.inputs, 'linux-amd64')
        for change in ('failed', 'not-run', 'go-hosted', 'source', 'target', 'hash', 'run'):
            with self.subTest(change=change):
                bad = copy.deepcopy(report)
                if change == 'failed': bad['status'] = 'FAIL'
                if change == 'not-run': bad['checks'][0]['status'] = 'NOT_RUN'
                if change == 'go-hosted': bad['checks'][0]['engine'] = 'go-hosted'
                if change == 'source': bad['source_sha'] = 'b'*40
                if change == 'target': bad['target'] = 'windows-amd64'
                if change == 'hash': bad['hashes']['cli-D'] = 'b'*64
                if change == 'run': bad['run']['id'] = 'another-run'
                with self.assertRaises(ValueError):
                    gate(bad, self.compiler, self.inputs, 'linux-amd64')

    def test_unsafe_archives_never_write_outside_destination(self):
        for names in (['../escape'], ['/escape'], ['C:/escape'], ['x\\escape'], ['pkg/a', 'pkg/a'],
                      ['pkg/A', 'pkg/a'], ['pkg/a', 'pkg/a/b']):
            for kind in ('zip', 'tar.gz'):
                with self.subTest(names=names, kind=kind):
                    path = self.root / ('bad.'+kind)
                    if kind == 'zip':
                        with zipfile.ZipFile(path, 'w') as z:
                            for name in names: z.writestr(name, 'unsafe')
                    else:
                        with tarfile.open(path, 'w:gz') as t:
                            for name in names:
                                info = tarfile.TarInfo(name); info.size = 6
                                t.addfile(info, io.BytesIO(b'unsafe'))
                    with self.assertRaises(ValueError): extract(path, self.root / 'out')
                    self.assertFalse((self.root / 'out').exists())
                    self.assertFalse((self.root / 'escape').exists())

    def test_links_are_rejected(self):
        path = self.root / 'bad.tar.gz'
        with tarfile.open(path, 'w:gz') as t:
            info = tarfile.TarInfo('pkg/link'); info.type = tarfile.SYMTYPE; info.linkname = '/tmp'
            t.addfile(info)
        with self.assertRaises(ValueError): extract(path, self.root / 'out')

    def test_packaging_both_formats_has_exact_inventory_and_no_dev_files(self):
        report = self.report()
        source = self.root / 'source'
        (source / 'selfhost/resources').mkdir(parents=True)
        (source / 'selfhost/cli').mkdir(parents=True)
        (source / 'selfhost/resources/bunko_data.mio').write_text('legacy importable source')
        (source / 'selfhost/cli/main.mio').write_text('mio v2.0.0-dev (pure Mio Native AOT; GF3 candidate)')
        (source / 'LICENSE').write_text('license')
        for name in ('kiso/math/integer.mio', 'kiso/math/integer_test.mio', 'kiso/snap.before-patch/old.mio', 'kiso/math/test.sh'):
            p = source / 'bunko' / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('source')
        prepare(source, self.inputs['source_sha'])
        self.assertEqual((source / 'selfhost/resources/bunko_data.mio').read_text(), EMPTY)
        for target in ('linux-amd64', 'windows-amd64'):
            report['target'] = target; report['seed'] = dict(status='NOT_RUN')
            rp = self.root / 'report.json'; rp.write_text(json.dumps(report))
            archives = package(source, self.compiler, rp, self.root / target, target)
            binaries = []
            for i, archive in enumerate(archives):
                dest = extract(archive, self.root / (target+str(i)))
                manifest = json.loads((dest / 'manifest.json').read_text())
                self.assertEqual(inventory(dest), manifest['files'])
                binaries.append(next((dest / 'bin').iterdir()))
                self.assertFalse(any('test' in n or 'before-patch' in n for n in manifest['files']))
                self.assertEqual((dest / 'bunko/kiso/math/integer.mio').exists(), i == 1)
            self.assertEqual(digest(binaries[0]), digest(binaries[1]))


if __name__ == '__main__': unittest.main()
