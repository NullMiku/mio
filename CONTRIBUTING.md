[English](CONTRIBUTING.md) | [简体中文](docs/CONTRIBUTING.zh-CN.md) | [日本語](docs/CONTRIBUTING.ja.md)

---

# Contributing to Mio

Bug reports, documentation fixes, additional tests, Bunko standard-library extensions, compiler optimizations, platform ports, and architecture proposals are welcome. For bug reports, include a minimal reproduction, the Mio version, operating system and architecture, expected behavior, and actual output.

## Governance and design

Mio uses a **maintainer-led governance** model. Contributors may propose designs, join discussions, and submit implementations; maintainers make the final decisions about language design, technical direction, and PR merges. Maintainers should explain reviews and decisions clearly, reasonably, and respectfully. Declining a design does not imply anything about a contributor's technical ability.

Reviews prioritize consistency of language design, long-term maintainability, and architectural integrity. Current directions include native AOT, self-hosting, a clear and strict type system, and modular architecture. Keep the core small and treat ABI, runtime, GC, and platform compatibility changes carefully. Avoid adding global complexity to accommodate one feature. These principles guide exploration without ruling out future approaches.

## Getting started

Fork the repository on GitHub, clone your fork, and create a topic branch from the appropriate development branch. Open a PR against the corresponding upstream branch and complete the template. Replace the example fork name and branch name below:

```bash
git clone https://github.com/YOUR-NAME/mio.git
cd mio
git switch -c fix/topic
```

This branch is `Mio-2.1`. Official source builds retain the trusted Native Seed and the self-hosted Mio compiler architecture. On macOS ARM64, the command interface is:

```bash
"$MIO_NATIVE_SEED" build selfhost/cli --bunko-root "$PWD/bunko" -o /absolute/new/path/mio
```

The required trusted Seed version and SHA-256 checks are described in the testing documentation. Go (see `go.mod`) is used only for the reference frontend/VM, supplementary testing, and generating a go-hosted Stage A when no trusted Seed is available. No Go program generates native code: the Go AOT backend has been removed. The unified test driver uses Bash, Python 3.9+, and Git; native signing checks use macOS `codesign`. None of these are new dependencies of the released Mio compiler.

Common commands:

```bash
bash scripts/ci/selftest.sh
# On an Apple Silicon Mac with a trusted Seed:
bash scripts/ci/run.sh macos-arm64 all quick
# On Linux, run the supplementary reference implementation only;
# this does not replace native acceptance testing:
bash scripts/ci/run.sh linux-amd64 go-reference quick
```

See [testing](docs/testing.md) and the [testing audit](docs/testing-audit.md) for command coverage and observed results. The implementation environment described by the current audit was Windows; commands not executed on a platform are not reported as passing.

## Discuss changes in advance

For changes to language syntax, types, the core runtime, GC, ABI, major compiler architecture, new backends, or large dependencies, consider opening an Issue first. Explain the problem, alternatives, compatibility impact, and verification approach. Early discussion can avoid wasted effort while leaving room for technical experiments.

## Commit and PR scope

Existing commits use concise prefixes such as `feat(bootstrap): ...`, `fix(aot): ...`, `docs: ...`, and `chore: ...`. You may use `feat`, `fix`, `test`, `docs`, `refactor`, `ci`, or `chore` with an optional scope. Explain the concrete change and why it matters. Chinese and English are both acceptable; rewriting history solely for naming consistency is not required.

Keep each commit a reviewable logical unit. Separate unrelated fixes, broad refactoring, and feature work into distinct PRs; include related tests and documentation with the implementation. Avoid incidental formatting churn, generated artifacts, personal configuration, or unrelated code changes.

## Testing evidence

**Mio's native testing framework is the primary testing mechanism. External tools and other programming languages are permitted for supplementary testing and independent cross-validation only.**

Contributors should prioritize tests written in Mio for ordinary modules, standard-library code, and Core/AOT/GC components, then independently verify critical functionality. Record the results of the native and independent layers separately. If the framework cannot yet handle a test category, explain the limitation before using an auxiliary tool. Tests written in other languages are not part of Mio's official implementation.

Independently testable modules should provide a `test.sh` and adjacent `ci-module.json`. Existing packages without their own entry points are tracked in the testing documentation; new modules should follow this interface. Reuse shared environment checks, logging, and reporting rather than copying entire test harnesses.

In a code PR, include the commands actually run, the target platform, results, and logs. Distinguish `PASS / FAIL / SKIP / NOT_RUN`, and explain skips. A test that was never run, an empty test, or cross-compilation alone must not be presented as a pass.

New features generally need tests; bug fixes should add regression tests when practical. Compiler, code-generation, AOT, ABI, runtime, GC, and self-hosting changes require both formal tests and an independent way to judge results. Re-running `mio test` does not count as independent verification. Test infrastructure should also run negative self-checks to confirm that deliberately broken cases produce nonzero exit codes.

## External tools and Core isolation

Go, Shell, Python, and other external tools may be used only as **development or CI dependencies** for supplementary verification, evidence collection, and infrastructure self-checks. They may invoke Mio, but Mio Core, its standard library, and the official compiler must not import, link, or invoke them at runtime. New test dependencies must not participate in official source builds, execution, or self-hosting.

Official release archives must exclude test drivers and their test-only dependencies. The existing `tools/native-ci` is implemented in Mio; production builds retain the empty-PATH environment, existing execution sandbox, and trusted Native Seed. The added `scripts/ci` tools run outside that sandbox. PRs changing packaging should include source-dependency checks, an actual archive inventory, and evidence of building/running without test tools. Unavailable release checks must be marked `NOT_RUN`.

Distinguish historical Go bootstrap/reference code from any newly added test-only tools. Do not replace the established native Mio Seed build process for the sake of tests or put test tools into release archives.

## Review criteria

Maintainers consider correctness, regression risk, architectural consistency, performance, cross-platform behavior, testing, maintainability, documentation, and long-term direction. **Passing tests is necessary evidence, not an automatic promise to merge.** Report existing baseline failures and known limitations honestly; never hide failures by deleting important checks, changing expected results, or skipping tests.

## License and attribution

Source code and associated documentation follow the repository's [MIT License](LICENSE); preserve copyright and license notices. Contributors must have the right to submit their work and identify third-party code and its license. No contributor license agreement (CLA) or copyright assignment is introduced here.

Mio and Mochi illustrations under `assets/mascot/` are **not covered by the code's MIT License**. Their copyright and usage terms are separate.

## AI-assisted development

AI assistance is allowed. State in the PR whether you used it. Submitters must understand their changes and remain responsible for correctness, security, license compliance, and test results. AI-written testing reports do not replace actual execution evidence.

## CI V2 entry points

For ordinary PRs, `ci-pr.yml` produces a conservative Quick plan, then invokes `bash scripts/ci/run.sh <target> <modules> quick`. Pushes to `Mio-2.1`, manual runs, and scheduled Full checks use `ci-full.yml` and the same entry point with `all full`. For a single-module change, use that module's `test.sh <target> [quick|full]`. The release workflow remains separate.

Native tests first use a trusted Seed to build the compiler from the current working tree and then reuse the result to test modules. Running only historical behavior embedded in the Seed does not prove the current source passes. New independent modules need adjacent `ci-module.json` and `test.sh` files and real Mio tests. Critical modules also need fixed-output, byte-level, exit-code, or reference-implementation oracles. The shared `ci_native_and_crosscheck` helper can continue collecting independent evidence after a native-layer failure, but the final status must still be nonzero.

Attach the commands, platform, and `report.json` to validation evidence. Separate `PASS`, `FAIL`, `SKIP`, and `NOT_RUN`; all-skipped or empty checks cannot be called successful. For CI infrastructure changes, run `bash scripts/ci/selftest.sh` and check workflow syntax. Do not conceal known Core failures by changing assertions, weakening expectations, or skipping tests. See [testing architecture](docs/testing.md) and the [audit](docs/testing-audit.md).

Compiler, backend, runtime, or GC changes must pass the three-platform native workflow at `.github/workflows/native.yml` (`Native / required`). Changes to the [Runtime ABI contract](docs/runtime-abi.md) must update `tests/runtime-abi`. Only isolated changes to ordinary standard-library test files may narrow Quick; implementation code, Core/ABI/GC/AOT, manifests, and unknown changes use the full Quick scope. macOS currently uses GitHub-hosted `macos-15`.

**Temporary measure:** A trusted Native Seed is not yet available on GitHub-hosted runners, so Native Verification is currently `NOT_RUN`. It will resume only when `MIO_NATIVE_VERIFICATION=enabled` is set and the Seed is provided. A passing `Mio CI / required` gate currently covers supplementary checks only; it does **not** prove native verification passed. See [testing architecture](docs/testing.md) and the [three-tier CI scheduling audit](docs/ci-scheduling-audit.md).
