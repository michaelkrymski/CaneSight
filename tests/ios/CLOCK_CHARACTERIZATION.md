# CS-013 clock and lifecycle characterization

The manual Pi clock observer uses only its private Pi-role six-field JSON and
the existing verified WSS/clock relay. No operator/phone token on Pi, no camera,
GPIO or motor output. Host runs only
LiveDepthPairTests/testClockCharacterizationDepth with fresh phone-role file at
Documents/cs013-clock-pair.json, delivered via normal USB file copy. It consumes
that file, captures real frames, and sends for 65 seconds. No normal-app streaming.
Pi has a 150-second observation deadline and 300-second private-file enrollment wait.
Use a fresh source/process boot for every execution. No automatic Pi SSH.

Twenty calibration exchanges spanning at least twenty seconds constrain the
affine model phone_time = alpha + beta * receiver_time using causality:
alpha + beta*t1 <= t2; alpha + beta*t4 >= t3. Pairwise elimination of alpha gives
an interval for beta without assuming symmetric network delay. Freeze this
calibration range. At least twenty separate holdout exchanges must remain jointly
consistent with it; never refit the original range using holdout. Inconsistency
latches failure. The maximum absolute ppm endpoint is a CANDIDATE under the
explicit constant-rate assumption, not a guaranteed oscillator specification.

For measurement only, the accepted protocol ClockBound helper widens the latest
exchange using that candidate and computes conditional age intervals. Report
packet counts satisfying the existing 500 ms age / 100 ms half-width rules, and
unmapped/rejected counts separately. These computations do not configure the
production receiver or authorize guidance. No synthetic zero/default drift is used.
The production default remains unknown until the clock model/operating envelope
and resulting budget receive independent integration review; finite samples cannot
prove arbitrary future temperature, sleep or rate-change behavior. Record the
measured model and assumptions honestly instead of presenting RTT as capture age.
Reference for the distinction between observations and assumed worst-case clock
frequency tolerance: RFC5905 section7.2, https://www.rfc-editor.org/rfc/rfc5905.html#section-7.2

Phone lifecycle evidence uses actual scene activity. --lifecycle-probe writes a
bounded local record of active flag and known-column counts before/after existing
AppServices.setActive; no timestamps, IDs, images or distance values. Normal runs
do not write it. Actual operator-assisted lock test verifies background state,
real depth recovery and Stop Unknown; inspect the separate device count record
to confirm clearing occurred before recovery. This is local host verification,
not paired receiver expiry, kernel deep-sleep or CS-017/CS-030 task takeover.

The assisted lock test opts in using CANESIGHT_OPERATOR_LOCK_TEST=1 in the UI
runner test environment (xctestrun EnvironmentVariables). Normal full suites skip
this manual test instead of waiting for an operator. The actual recorded lock run
preceded this selection guard; its tested source hash is retained in evidence.

After twenty separate holdout exchanges pass, an isolated test CaptureAgeGate is
constructed with the measured candidate ppm for this same controlled run. It
requires its own newly issued/matched calibration and fresh ready heartbeat,
then admits only original captures inside accepted age/uncertainty budgets. It
runs independent expiry ticks and clears on transport close/model inconsistency.
Report these bench observations separately from simpler conditional interval
statistics. This is an actual instance of the unchanged receiver implementation,
not a production configuration change or an unconditional physical drift claim.
