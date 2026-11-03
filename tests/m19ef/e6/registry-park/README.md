# Registry acquisition after a completed parked epoch

The native protocol component executes the actual generated registry_lock with
explicit clock and gc_poll completion inputs. It does not execute a collector
and never counts as concurrent GC acceptance. A completed park advances the
production thread_seen_epoch publication; no-progress and continuous-progress
controls preserve the one-second soft and original thirty-second hard limits.
The preserved before factory must still produce the false timeout2. Actual
Collector/Mutator epochs and all full gates must pass separately.

E5 epochs-19 in E6-main-los-20261103-01 remains FAIL. Its actual error PC was
attached_heap_enter -> gc_heap_enter, status2. This component establishes a real
soft-deadline defect; the exact failed Epoch is not relabelled or retried.


`resume.mio` tests the legal next-owner publication between observing zero owner
and recording completion. Before repair it records seen8 while actual ack7;
after repair it records the last actually acknowledged completed Epoch7.
No new epoch, timeout or field layout is fabricated in production. The test
supplies the interleaving at the explicit IR seam only; actual GC stress remains
an independent requirement. The before factory and complete signed image hash
are retained and reproduced separately.
