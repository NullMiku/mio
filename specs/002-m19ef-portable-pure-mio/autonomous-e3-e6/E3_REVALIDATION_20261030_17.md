# E3 revalidation candidate17 — PASS

The same bounded ordinary Worker path accepted in candidate16 passes again after
fixing cooperative registry progress deadlines and non-null local lambda value
analysis. No TLS/Shadow Frame/Safepoint implementation was replaced.

Frozen input manifest SHA256:
`6fa8e1b4be91fc40274ddae23ceda5167be7b632f10f8f9466f2050c57a6e2f8`.
Evidence: `build/m19ef-evidence/E3-workers-20261030-17/`.
The identical manifest also passed the scoped typed SATB matrix in E4 candidate07.

All538 commands met expected exits.372 ordinary Worker runs,32 native package
tests,64 real managed-heap repetitions, earlier main-only compatibility samples,
and11 historical GC images pass. Whole signed bytes of those11 legacy images
still match their GF4 D compatibility baseline; this is NOT a new fixed point.
Negative bindings, slot/snapshot limits, OOM, Native blocking/FIFO/report/spawn
cases retain expected failure exits. Final source-unchanged check passes.

Actual ordinary traces total133994 Minor and8802445 Major collections. The high
Major count includes the intentional GC loop during real subprocess spawn/wait.
Total child wall823.052s, CPU823.900s, largest child peakRSS1793916928B (includes
compiler processes). GC pause percentiles N/A; no complete pause sampling yet.

`E3-acceptance.json` is the reviewed overlay; original conservative summary.json
is preserved. G3.1–G3.7 remain PASS within E3_FINAL_REPORT's documented bounds:
one main and two reusable joinable Workers, automatic typed roots/native waits,
1000 snapshot roots, native machine-word bridge bindings. No public portable
thread API or unsupported platform acceptance is implied.

E4 remains IN_PROGRESS. Allocation/Minor cooperation is the NEXT implementation
increment; bulk writes, queue compensation, repeated epochs and full mark gates
remain unfinished. E5/E6 NOT_RUN, M19e NOT_ACCEPTED. No commit/push/tag/release.
