# Native candidate CI and legacy release separation

This is a visible implementation of the user's highest-priority Pure-Mio
architecture constraint. It is not permission to publish and does not alter any
historical GF0/M19 audit result.

The active release.yml now builds the Pure-Mio development candidate through the
native Mio program in tools/native-ci. The previous Go/Python production release
workflow is preserved byte-for-byte at .github/legacy-workflows/release-go-reference.yml.
Legacy Go tests, VM/reference implementation and Race CI remain in their separate
existing workflow. No existing native semantic, GC or compatibility gate is
removed or weakened. A legacy reference tool cannot become an implicit formal
compiler/build dependency under the Pure-Mio architecture.

This intentionally changes release automation: no Go-built product or automatic
public Release is produced by the active candidate workflow. Its only tag is the
current development tag v2.0.0-dev, with explicit version validation and read-only
permissions; manual execution is also available. Future stable version/tag and
public publication policy require an explicit maintainer action and appropriate
source/version acceptance. The agent creates no commit/tag/release and uploads
nothing. The old current V2.0.0/M19 release-policy readiness remains independently
NOT_ACCEPTED where its historical Race gate is unresolved; native acceptance is
not a claim that old go test -race now passes or that public release is READY.

GF5/native A12 acceptance must cite an actually executed local native pipeline,
complete source/candidate hashes, native tests, package and isolated install.
Static workflow validation alone cannot pass that gate. Remote hosted CI and
public Release must remain NOT_RUN when not actually executed. All official
native build/test/hash/provenance/package/install computations are Mio Native;
external audit controllers only provide independent isolation/measurement checks.
