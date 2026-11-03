# GF3 regexp compatibility disposition

This records existing behavior; it adds no product functionality and changes no
frozen test input, reference output or raw failure. The final-r2 candidate is
bound to the source manifest in `GF3_FINALIZATION.md`'s final evidence directory.

The complete frozen 9030-case matrix executes through final-r2's ordinary offline
CLI and embedded Bunko: 8846 results exactly match the isolated historical Go
reference; 184 differ. Every difference is a valid Unicode script property name
which that reference rejects, while Mio accepts and matches the unchanged Unicode
15 range/stride facts. Both positive and negative scalar boundary cases are
independently checked. No reference-accepted match in this matrix regresses.

The historical parser canonicalizes property names before looking them up in
`unicode.Scripts`. Multiword table keys are not canonicalized by that lookup.
See the primary [Go 1.25.9 parser, canonicalName and unicodeTable](https://raw.githubusercontent.com/golang/go/go1.25.9/src/regexp/syntax/parse.go).
Mio's existing normalized property lookup resolves these valid names. This is a
visible Unicode property extension, not exact Go rejection parity. For example,
`^\p{anatolianhieroglyphs}$` accepts U+14400 and rejects U+143FF.

Disposition: retain the correct Unicode property behavior and explicitly record
it as an intentional compatibility extension under acceptance A10. Reproducing a
reference rejection would remove already implemented, independently verified
functionality. Do not claim 9030/9030 exact reference equality. The complete raw
184 FAIL comparisons remain in
`build/gofree-evidence/GF3/final-r2/regexp/raw-exact-reference-results.json`,
with their separate classification in `unicode-extensions.json`; unresolved
semantic differences are zero. This disposition does not waive any missing,
failing or unexecuted semantic, GC, CLI or bootstrap gate.
