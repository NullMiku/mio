# GF3 finalization — scope and evidence discipline

User instruction 2026-10-27: stop broad feature expansion. Finish diagnostic,
color and path repairs; freeze one complete final source snapshot and one unified
CLI candidate, then perform the required regressions. Only actual success of all
required GF3 gates permits GF3 PASS and automatic transition to GF4.

The Pure-Mio architecture and all semantic/GC/compatibility requirements remain
unchanged. No tests or historical failures are removed. A failed final candidate
is retained with its source/candidate hashes and failures; a repair requires a new
snapshot/candidate and revalidation. Passing an older snapshot is not final proof.

Native source IR v16 and v14/v15 compatibility follow TYPED_CALL_IR_V16.md. Source
diagnostics retain the published E0001/E0101/E0201/E03xx classes and human/short/JSON,
color and verbose controls. The previous development-only E_PARSE transport string
is retained in verbose native build causes; it is not the final source diagnostic
schema. Fixed historical v14/v15 input artifacts are never relabelled as v16.

Path identities distinguish existing physical files/directories from memory-only
virtual directories and unsaved files in real directories. Client URIs remain
unchanged in LSP responses. Test image selection must use the exact package key
recorded when the plan was compiled, including relative and aliased input paths.
Explicit Bunko roots never silently fall back to embedded or other disk sources.

The final evidence set records: exact source manifest and SHA256, complete signed
and unsigned candidate SHA256, native builder provenance, actual commands and
outputs, isolation policies, semantic/native/GC outcomes and all unresolved gates.
Auxiliary audit scripts/reference data stay outside the formal build chain. GC
API witnesses, when used, must be Mio source built/signed by the same candidate
from the same frozen compiler core, identified separately from normal CLI builds.
They cannot substitute for GF4's full unified CLI multigeneration source chain.

Unicode regexp reference differences must retain raw comparison results. A
separately verified correct property extension cannot be called exact reference
parity. Any compatibility disposition must be explicit and source backed, never a
changed expected result hidden in a PASS count.

The explicit Unicode property compatibility disposition is recorded in
[REGEXP_COMPATIBILITY.md](REGEXP_COMPATIBILITY.md). It preserves the full raw
matrix and distinguishes exact historical parity from independently verified
Unicode extensions; no product source changes are made by this disposition.
