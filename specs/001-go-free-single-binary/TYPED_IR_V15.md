# Native typed IR v15 — implementation amendment

This amendment implements the user's Pure-Mio architecture constraint. It does
not change GF0 historical artifacts or the v14 legacy encoder API. Its gates
remain IN_PROGRESS until execution evidence is recorded.

The native frontend must preserve source-declared representation constraints
when value-flow inference has no constructor witness. An empty dependency array
must not prevent compiling code that reads a declared integer record field.
Supplying dummy objects or weakening unknown-pointer rejection is prohibited.

Mochi v15 adds `OpTypeConstraint` (opcode 66), followed by one unsigned byte.
It requires one operand-stack value and preserves that exact value and stack
depth. The byte uses existing non-nullable representation descriptors:
1–5 and 7–17. Descriptor 0, reserved 6, and all nullable-bit encodings are
invalid. This instruction constrains the value's base representation; it is
neither a cast nor proof of non-nullability. Existing nullable propagation,
runtime nil errors, type conflicts and precise GC verification remain active.
The native backend emits no machine instruction for this static constraint.

The first implementation emits these constraints for checked field expressions.
This is not yet a claim of complete generic type metadata: unresolved generic
specialization and nested empty-container cases must still be investigated and
accepted without fabricated witnesses.

The native source generator additionally materializes generic function bodies
from the checker's call-site type substitutions. A concrete instance is keyed
by declaration package/name and its ordered checked type arguments. Repeated
calls share an instance; recursive calls reuse an identity reserved before body
emission. Every reserved instance must receive a real body before compilation
can succeed. Cross-package arguments retain their qualified type identities
when copied into the declaration package's type table. Nested calls and returned
closures use the active concrete bindings. Type parameters remain lexical type
bindings and never become runtime closure cells. Invalid instantiated container
types must fail type checking rather than reach native layout generation.

Instance selection must not depend on a runtime argument, a nonempty array, a
constructor witness or a returned value. Source-driven specialization does not
change the descriptor encoding above or weaken nullable and GC checks. These
requirements need final unified CLI, native execution and bootstrap evidence;
development component tests alone do not establish generic acceptance.

Normal native source and test compilation share `compile_native_modules` and
the same Mio checker, generator and backend. The decoder, disassembler and
native executor accept existing v1–v14 modules and v15. A v14 module containing
opcode 66 must still fail. The legacy codegen APIs continue to encode v14 for
frozen-reference comparisons; they are Mio implementations, not an external
compiler or runtime fallback. Old reference tools are not expected to consume
v15 and are excluded from the formal dependency chain.

Required evidence:

- Canonical v15 round trip and rejection of invalid descriptors/version use.
- Conflicting scalar constraints and missing stack operands fail closed.
- A nil-only constrained scalar remains nullable.
- Complete native checker tests, including empty dependency callers and closure
  fact isolation, execute and pass without test-specific input changes.
- Existing v14 decoding, unknown-opcode rejection, nullable/GC regression suites
  and final single-process CLI behavior pass on the final source snapshot.
- Value-free, recursive, cross-package and closure-returning generic functions
  compile and execute with distinct concrete types, including nested containers,
  and invalid instantiated array/nullable types fail at the frontend.
- Native multigeneration bootstrap uses the same typed frontend/backend core;
  no Go/Python/C/LLVM compilation stage is introduced.

All earlier failures remain evidence; no GF phase is promoted by this amendment.
