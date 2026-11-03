# E3 final E4-source revalidation18 — PASS

G3.1–G3.7 pass on242 frozen Mio inputs, Manifest `d7e36e3e3bd280cedb9b5c6c7394bae1ccd6710976211af81ffc5ab136a8275e`. Evidence:
`build/m19ef-evidence/E3-workers-20261030-18/`; reviewed `E3-acceptance.json`.
All538 commands met expected exits/no timeouts;372 ordinary Worker runs,32 native
tests,64 actual managed heap repetitions and11 historical GC witnesses pass.
Ordinary programs use compiler-generated TLS/precise roots/polls and real native
threads, including blocked input/output/report/spawn, exits, reuse, closures,
recursive/typed roots, Young/Old/LOS and expected negative limits/OOM.
The whole signed11 GF4 images match for compatibility only, NOT a new bootstrap.
Before/after source hashes match the accepted E4 candidate08 exactly.
Measured child wall902.501s, CPU898.081s; pause percentiles N/A.
Original conservative controller summary retained. Bounded one main+two reusable
Workers,1000 exact roots,8MiB Worker stacks; no unsupported target acceptance.
E4 acceptance is separate; E5/E6 NOT_RUN, M19e NOT_ACCEPTED.
