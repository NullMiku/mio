# Native Mio candidate CI

The production entry is Mio source, compiled by the existing unified CLI:

```
/path/to/trusted/mio run tools/native-ci --bunko-root /absolute/source/bunko -- ci /absolute/source /path/to/trusted/mio /absolute/new-output uncommitted-worktree
```

Run from the source root. Output must be new, its parent must exist. The accepted
compiler snapshot is deliberately pinned:149 canonical compiler/library/test
sources, manifest7f9a2718b3270a9fb40415c210cc232e8324177866b0127962a63057440bdfee;
trusted GF4 native Seed4c3f7dcbea536d756c3c4a93c18a999412625184bd5c90123f1c16a0cd9e36da.
Unknown source/seed revisions fail rather than borrowing an unrelated binary.
Changing this certified snapshot requires new source/bootstrap acceptance.

The ordinary Mio run program is a visible native orchestrator, not another
installed compiler. It invokes the one trusted native mio for complete source
rebuild and native test discovery/execution. That build runs its shared frontend,
IR, backend/runtime generation and signing in one process. The orchestrator
implements resource/source verification, hashes/provenance, archive creation and
installation in Mio. No Python, Go, C compiler, linker, shell build script,
external tar/gzip or external signature creation participates.

The pipeline actually rebuilds the current complete compiler source and requires
the complete result to equal the certified GF4 fixed point. This CI run records
one source rebuild; it does not fabricate another four-generation execution.
The actual Seed→A→B→C→D provenance and full B=C=D evidence remain the independent
GF4 acceptance prerequisite. It then runs native selfhost, Bunko and archive
suites; actual runtime emitter metadata probes; packages and installs the result;
and compiles/executes an application with installed embedded Bunko. Exact
component/fixture hashes and source revision are recorded as well as the core.

The archive contains only mio, LICENSE and README.txt. Its ustar headers have
fixed owners/times; gzip uses deterministic stored DEFLATE blocks with CRC32 and
ISIZE. It follows [RFC1951](https://www.rfc-editor.org/rfc/rfc1951) and
[RFC1952](https://www.rfc-editor.org/rfc/rfc1952). The native installer validates
the complete archive and expected image hash before creating a new prefix,
rejects duplicate/unsafe entries and preserves existing installations. These
private package readers accept the deterministic format produced here.

```
mio run tools/native-ci -- package /path/to/mio /path/to/LICENSE /absolute/new-package
mio run tools/native-ci -- install /path/to/archive.tar.gz /absolute/new-prefix <expected-mio-sha256>
```

Packaging-only mode is explicitly not a source-build/CI acceptance claim. The
normal install contains one toolchain executable, mio; no extra compiler, disk
Bunko or runtime is required. Local ad-hoc signing is not Apple notarization.

The workflow uses a pre-provisioned trusted native Seed in MIO_NATIVE_SEED on a
macOS ARM64 self-hosted runner. Checkout/process launch and OS sandbox enforcement
are runner infrastructure; all build/test/package/install logic is Mio. The
sandbox restricts executable paths to the seed and generated native programs,
denies network access and protects source files. PATH hiding alone is not proof.
It is read-only and has no Publish job or release credentials. Actual hosted
execution/publication remain NOT_RUN until performed by the maintainer.

Legacy Go/Race CI remains separate in ci.yml. The previous Go-based release
workflow is preserved byte-for-byte at .github/legacy-workflows/release-go-reference.yml;
it is not a native product build dependency. Historical M19 Race nonacceptance
is not rewritten or claimed fixed. See specs/001-go-free-single-binary/NATIVE_CI_POLICY.md.
