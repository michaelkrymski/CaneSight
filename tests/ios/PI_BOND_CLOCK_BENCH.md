# Isolated Pi/phone clock measurement with saved enrollment

This bench uses the existing Pi bond. It does not provision a credential, use
camera/GPIO or configure production drift. The phone must stream real fresh depth.
It measures 20 calibration exchanges over at least 20 seconds, then separate
holdouts under an explicitly assumed constant affine relative clock rate. A
finite-run feasible rate interval is not a hardware drift guarantee, and conditional
age calculations are not permission for physical guidance.

Stop only the Pi's existing bond poller/receiver before running this exclusive
measurement peer; competing Pi process identities will rotate/revoke each other's
sessions. Do not stop or modify motor drivers as part of this helper. It never
arms or operates them. Notify the phone operator when this receiver starts so the
phone can reconnect to the new measurement process epoch if needed. Its process
boot identity changes; saved bond credentials do not. Partial models are discarded
on session or peer changes, never combined across Pi reboots.

The local source-only archive contains no credential, image, model or Git data.
It includes the existing protocol/diagnostic Python modules needed by the helper.
No GitHub access or update is necessary. Commands below use the Pi's previously
working virtual environment. A missing dependency must be resolved before claiming
measurement; do not disable validation or TLS checks.

On the Mac, in your own Terminal (enter the SSH password there, never in chat):

```sh
bash /Users/michaelkrymski/Documents/CaneSight/tests/ios/copy_clock_bench_to_pi.sh
```

This copies the source/document/schema files into
`/home/interfere/canesight-local-demo/clock-bench/`, preserves relative paths and
checks SHA-256 hashes on the Pi. It copies no credential and starts no test. It
does not remove unrelated existing files or change the saved Pi enrollment.

When separately instructed to run the measurement, on the Pi after stopping its
other saved-bond poller/receiver:

```sh
cd /home/interfere/canesight-local-demo/clock-bench
read -r -p 'Path to your EXISTING Pi bond JSON file: ' CS013_PI_BOND_FILE
chmod 600 "$CS013_PI_BOND_FILE"
PYTHONPATH=. "$HOME/.venvs/canesight-pr32/bin/python" tests/ios/pi_bond_clock_probe.py --bond-file "$CS013_PI_BOND_FILE" --exclusive-pi-peer --seconds 75
```

The prompt requests a file path only. Do not paste JSON or a token. This source
bundle does not modify your repository, existing credential or installed packages.
It creates no GPIO output. Do not invoke backend provisioning tools.

Send the final JSON summary back to the phone operator. It includes packet rates,
matched RTT/width diagnostics, finite-run affine constraints/holdout consistency
and explicitly conditional age results. It excludes credentials and raw images.
If it reports a failure, send only that failure line. Socket/peer changes discard
the partial model; they are not valid evidence for the new session.

After the helper exits, restart your usual Pi saved-bond client. That process may
require the phone to reconnect again. No automatic service changes or motor state
restoration are performed. Keep capture-age eligibility unknown unless its actual
receiver requirements are independently met. Never promote an observed sample
rate interval to a general oscillator or sleep/resume drift bound.
