# Native typed indirect calls — IR v16

This implementation amendment preserves the Pure-Mio architecture and all GF0
history. It does not promote GF3 or any acceptance gate.

Native source code generation emits OpCallTyped (67): opcode, a big-endian
uint16 argument count, and a uint8 return flag (0 = unit, 1 = one value). Its
width is four bytes. It consumes the callable and exactly the argument count,
and pushes exactly the stated return count. Flags above 1 are invalid.

The checked Mio source result type supplies this metadata. The backend still
must prove the actual callable targets, argument representations, result
representations, capture layouts and GC roots. Every target must have the
encoded arity and return shape. The instruction supplies stack shape, not a
cast, function target guess, nullable proof or GC escape hatch. Nil callable
errors and conflicting actual target signatures remain errors.

This removes return-shape guessing for native source function-value calls,
including calls through structure fields inside boolean/arithmetic expressions
and unit callbacks. The old OpCallValue (45) decoding and validation path is
preserved for versions 1–15 and existing files. Opcode 67 is accepted only in
version 16 or later. Legacy public encoder APIs still emit v14; the frozen v14
and v15 artifacts must be tested independently, and must not be relabelled as
v16. OpTypeConstraint (66) retains its existing v15 contract.

Required verification: canonical decoding and invalid flag/version/truncation
rejection; matching typed value and unit calls; mismatched return/arity rejection;
nullable/capture/GC regressions; ordinary unified CLI source compilation and
execution of indirect field calls inside expressions; final-source full suites
and the native multigeneration bootstrap. No historical foreign interpreter is
a formal compilation dependency. Auxiliary diagnostic output is never a formal
candidate or bootstrap input.
