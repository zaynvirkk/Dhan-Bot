# CAS-only recorder repair — 20 October 2026

The operator narrowed scanning and funded execution to CAS_LAG_V1. Its signal,
candidate ranking, cash limits, IOC orders and dynamic exits are unchanged.
The separate seconds observer is disabled; outcomes/history stay available.

The full-chain subscription used in CAS-only mode must not exhaust the replay
journal before its reference and auction. Raw capture now uses the existing
15:05–15:45 IST monitoring window while CAS-only and flat. This is an evidence
scope, not a new signal clock. It retains the pre-CTS observations needed for
reference selection. An active lifecycle retains capture at any time, and
any authorized directional strategy retains all of its pre-open/full-day data.
Financial/order recording and broker recovery are unchanged.

The capture worker coalesces sparse receipts for at most 20ms or 256 rows before
its existing background compression/write. Every original byte, receipt and
processing timestamp, epoch and duplicate survives. Queue items are acknowledged
only by the existing durable writer. Idle tails flush on the deadline. The
512MiB cap, disk reserve, overflow/failed-write entry interlocks and three-second
shutdown drain remain in force. This reduces overhead and needless flat-CAS
history; it cannot guarantee full-day capacity in every future traffic regime.

Negative cases precede implementation: flat morning scope, reference boundaries,
directional bootstrap, exposed recovery, sparse grouping, bounded batch/tail,
lossless duplicate/sequence round trip and cap failure preserving prior bytes.
Connected-service streaming and learning tests also run before the full release
suite and production guard mutations. Their reports prove software behavior,
not a profitable strategy or tomorrow's broker fills.

The running account was flat before the authorized roster change, which placed
no orders. The verified source switch must preserve the CAS-only scanned/funded
allowlists, capital, normal route attempts, money caps and exit settings. No
extra route attempt is granted by this repair. Market/route checks remain live
conditions; today is a closed session.
