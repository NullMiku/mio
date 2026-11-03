# Mio Unicode table generator

`main.mio` is the native Mio generator for the regular-expression Unicode 15.0.0 tables. It reads the normalized data path from `input.config` and the output `.mio` path from `output.config`. Run it with the native Mio toolchain. It requires no Go, Python, C, Clang or LLVM compiler.

`unicode15.tables` is a vendored factual data snapshot: lowercase property name, `|`, decimal `(low, high, stride)` triples; the final `fold` record contains `(codepoint, next-simple-fold)` pairs. The property aliases are included as names. Categories and scripts match Unicode 15.0.0. The simple-fold graph excludes full multi-codepoint string folding, matching regular-expression case-insensitive rune semantics.

The initial snapshot was migrated in the isolated development audit `build/gofree-evidence/GF3/unicode-migration-r1/export.go` from the local Go 1.25.9 Unicode 15 tables. That historical exporter is not a formal build dependency. The authoritative current build inputs are the checked-in data and Mio generator; changing the snapshot requires independent Unicode compatibility validation. See `LICENSE-data` for the source data redistribution notice, also retained beside the generated Bunko source.

The native-generator candidate and its execution evidence are retained under `build/gofree-evidence/GF3/unicodegen-r1`. This does not by itself certify complete regexp compatibility or GF3 acceptance.
