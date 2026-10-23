#!/usr/bin/env bash
# Source-only copy. SSH password is entered privately by the human in Terminal.
set -euo pipefail
CS013_ARCHIVE=/Users/michaelkrymski/Downloads/CaneSight-clock-probe-20261018.tar.gz
python3 - "$CS013_ARCHIVE" <<'PY'
import sys, tarfile
with tarfile.open(sys.argv[1]) as archive:
    for member in archive.getmembers():
        name = member.name
        if not member.isfile() or name.startswith('/') or '..' in name.split('/'):
            raise SystemExit('Refusing unsafe source archive')
        if not (name.endswith('.py') or name in {
            'shared/protocol/v1/messages.schema.json', 'tests/ios/PI_BOND_CLOCK_BENCH.md', 'code-manifest.sha256'}):
            raise SystemExit('Refusing non-source archive member')
PY
ssh -o ConnectTimeout=8 interfere@192.168.0.32 '
set -e
umask 077
mkdir -p /home/interfere/canesight-local-demo/clock-bench
tar -xzf - -C /home/interfere/canesight-local-demo/clock-bench
cd /home/interfere/canesight-local-demo/clock-bench
sha256sum -c code-manifest.sha256 > /dev/null
printf "%s\n" "Copy verified; no test started and no credentials copied."
for CS013_FILE in tests/ios/PI_BOND_CLOCK_BENCH.md tests/ios/pi_bond_clock_probe.py tests/ios/pi_clock_characterization.py tests/ios/clock_characterization.py tests/ios/pi_phone_depth_probe.py tests/ios/pi_phone_transport_probe.py
do
    test -f "$CS013_FILE"
    printf "/home/interfere/canesight-local-demo/clock-bench/%s\n" "$CS013_FILE"
done
' < "$CS013_ARCHIVE"
