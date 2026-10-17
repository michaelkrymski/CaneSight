# CS-023 rolling duty review correction

Base: 89e15adab322ea299915f193cb6c9c6626d20739.
Branch: task/CS-023-capped-haptic-scheduler; PR #35.
Reviewed head: eba1ada572e6b2d90e1c195855e48e141410afc8.

Michael's verified PM review identified a reproducible cumulative overrun:
1900 ms usage plus a reserved 100 ms pulse stopped after 150 ms records 2050 ms
without an individual pulse exceeding 500 ms. Two added regression tests failed
on the prior implementation for delayed expiry and cancellation; an exact
2000 ms boundary case passed.

edge/haptics.py now checks actual recorded rolling usage in the common stop
path after clearing the active interval, avoiding double charge. Overflow
latches unavailable, stops the worker and requests both channels off, including
a still-active peer. Cancellation and expiry share that behavior. Exact cap
usage stays allowed; faults remain sticky. This contains observed overrun and
cannot undo elapsed activation or establish hard real-time/electrical behavior.

Tests actually run: all 41 edge tests passed on Windows/Linux Python 3.12
(28 scheduler plus 13 uploader); simulation finished both off with no GPIO.
Shared/repository/changelog/whitespace checks run through checked publishing.
Static task requirements unchanged. Physical CS-009 blocker still applies.
