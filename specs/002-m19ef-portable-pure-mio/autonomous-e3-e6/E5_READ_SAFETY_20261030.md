# E5 Full-mode read boundary audit — acceptance IN_PROGRESS

The previous blanket opcode>=30 rule took an all-Mutator heap epoch even for
length/nil/field/index reads. Such unnecessary stops narrow genuine concurrent
execution. Current Full mode retains EVERY solved opcode Safepoint; it separates
read-only execution from heap/metadata mutation. Default/Mark-only behavior is
otherwise preserved. Object header16B, side16B, LOS ABI and threshold unchanged.

| Operation | Full-mode rule |
|---|---|
| Nonnullable scalar global store | Release store; matching global Acquire reads; no heap epoch |
| Noncaptured nonnullable scalar local store | Private native slot; poll retained, no heap epoch |
| Captured Cell/reference store, allocation, array/map mutation | Existing owned epoch, SATB/remembered and initialization protection retained |
| Length/nil/immutable field/enum payload/tag/captured get/capacity | No metadata mutation; poll retained, execute read without an epoch |
| Index | No outer epoch only when result is not nullable raw scalar; boxing-sensitive case stays conservative |
| Mutable word array storage/element read | CPU adapter Acquire reads match existing Release publication |
| Result boxing | Existing runtime allocation obtains/retains its constructor epoch; no unrooted raw scalar is treated as a reference |

Safety: a reader cannot acknowledge a newly requested stop in the middle of a
nonallocating opcode. Minor/next Init/Remark wait for its next solved boundary,
where the resulting operands are precisely published. Concurrent Sweep claims
only the closed dead set from stopped Remark. A legitimately reachable old read
operand was marked live; a later birth/promotion is outside that claim set. A
replaced old storage that was live at Remark stays retained for that cycle. The
next snapshot cannot retire a reader's current temporary until it acknowledges.
No user integer-to-managed-pointer forging or foreign unregistered mutator is
supported by this bounded compiler bridge. Existing exact Root/type guards stay.

Actor observations now require same GC Epoch and phase2 on both sides of a real
object read plus an increase in the existing actual same-odd-batch clock count.
Each Actor publishes its own observed Epoch in numeric signal[8+id]. Main waits
for a current-Epoch Actor observation before final stopped finish/join, in
addition to all original progress/reclaim assertions. Query45 is ONLY an Acquire
read of existing counter672; it never calls the observer or increments anything.
This avoids turning a fixed amount of early User progress into an immediate STW
finish before the OS has run the asynchronous collector. Wait bounds, all32
samples, all8 epochs and all strict acceptance assertions remain. No collector
sleep, mock work, manual Root publication, sample retry or dropped failure.

All code generation/runtime/link/signing remains native Mio. Failed matrices,
including genuine zero-observation runs, remain saved. This audit is a proof
review, not a substitute for the pending full32 and same-source E3/E4 regressions.
