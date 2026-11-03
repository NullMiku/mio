# Native Go-free runtime audit fixtures

`runtime_metadata.mio.fixture` contains Mio test source intended to be copied beside
unchanged `bunko/kiso/aot/lower/*.mio` for package-private runtime emitter access.
It is not a replacement collector, installed compiler component or build input.
The ordinary unified native CLI compiles the copied package into an isolated
native test generator; that generator emits and signs the actual ARM64 runtime
probes in Mio. The audit controller only copies inputs and runs native binaries.

It preserves the ten existing M19b metadata cases (ages, remembered references,
promotion edge, major, precision, adaptive threshold, cross graph, alternating,
minor scanning, precision storage), and verifies actual shadow-frame pop followed
by major reclamation. The historical Go reference is not executed by this audit.

Run from the repository root with a verified native candidate:

```
python3 scripts/gofree-runtime-metadata-probe.py --candidate <native-mio> --output <new-evidence-directory>
```

Python here is auxiliary audit scheduling, never a formal compiler or release
step. Preserve every failed attempt and the exact runtime source/fixture hashes.

`unsigned_image_audit.mio.fixture` is the independent deterministic-signature
inverse used by GF4's image audit. Copy it to a temporary `.mio` file and compile
with the verified unified CLI. It accepts signed-image, unsigned-output and
metadata-output arguments. Recovery succeeds only when native re-signing gives
exactly every input byte; it records complete native SHA256 values. It never
supplies code or IR to a compiler generation. GF4 additionally compares complete
signed B/C/D files, so no signing difference is hidden by unsigned comparison.
