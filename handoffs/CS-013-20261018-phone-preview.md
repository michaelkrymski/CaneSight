# CS-013 first physical iPhone preview

Main base: 5dd5fa37009402b7eb7c9dbed3d20eacd4346c90.
App implementation: 3e9e781cdb427cc7760cfcd47baeb74f8bc4cff7.
Signing checkpoint: cf64ad8d2c610f448d297375915384ccc29f26ec.
PR: https://github.com/michaelkrymski/CaneSight/pull/69.

After the first-launch trust gate, Michael reported the exact on-phone status:
"live local preview; sensor timing and physical mapping unverified."
That status is emitted only after the native adapter returns processedFrame.
A subsequent devicectl launch succeeded. Record this as operator-reported local
depth processing plus tool-confirmed launch on iPhone 17 Pro Max / iOS 26.6.2.
It is not a measured capture-clock, depth-accuracy, physical mapping or WSS result.

Requested follow-up: changing numeric image-column values, Stop clearing all
columns, and background/lock/recovery requiring new captures. These results are
not prefilled. No code changed in this evidence checkpoint. Earlier initial
trust failure remains in its historical handoff; it is no longer the blocker.

Dependencies #62/#63/#64/#67 remain draft source; CS-001 remains unchanged.
No Done claim or main merge. All previous tests remain valid for unchanged code;
checked publishing runs shared structure/test/changelog/whitespace checks.
