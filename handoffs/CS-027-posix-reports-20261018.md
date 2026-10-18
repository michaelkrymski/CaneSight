# CS-027: private report platform review fix

Owner: bondmila. Branch: task/CS-027-context-button.
Starting PR head/base: c8783b3b184c21b1da866acf2129149ccdf90f0f.
Integrated accepted main: 3579db2 (including accepted narration PR #41 and storage #76).
Merge checkpoint: 9fbba24. Only generated CHANGELOG conflicted; regenerated it.

Michael requested changes on PR #58 after Windows rejected private temporary
report directories using POSIX mode checks. Chosen permitted resolution: explicitly
scope private reports to POSIX, rather than claim unimplemented Windows ACL privacy.

## Changes

- edge/context_report.py: reject unsupported report hosts before path operations,
  os.open or revision lookup. Optional omitted report remains a no-op. Existing
  private-directory, outside-checkout, exclusive create and 0600 guards retained.
- edge/context_gpio.py and edge/menu_bench.py: fixed unsupported-platform diagnostic
  and unsuccessful exit before input/audio/bench construction.
- tests/edge/test_context_report.py, test_context_gpio.py, test_menu_bench.py:
  explicitly scope five report-success cases to POSIX, plus four portable
  refusal/no-output/no-resource-start regressions. Existing POSIX symlink,
  overwrite, public-directory and checkout refusal tests remain.
- edge/CONTEXT_BUTTON.md: POSIX support, Windows refusal, report-required bench
  limits and correction of earlier platform-unspecified test claims.
- Own task runtime evidence, new changelog fragment and rendered CHANGELOG.

## Validation and limits

Before main integration: all 186 combined edge cases passed on macOS using the
existing external narration overlay; standalone 186 ran with 11 explicit missing
narration dependency skips. After integrating accepted main, final normal suite
results are recorded below. No source copies or test/privacy protection weakening.
Portable regressions simulate the unsupported-platform branch. No actual Windows
host run, new Pi/audio test, physical acceptance or production rollout is claimed.

This fixes report platform support only. Full task acceptance remains blocked on
production menu/request bridge, trusted route monitoring, evaluated observation
adapters and real paired phone/backend freshness. PM independent re-review is
required; ready PR is not Done. No new operator test is required merely for this
platform-report fix.

Final native-dependency edge suite on macOS: 186 tests passed, no skips.
Checked publisher runs root unit tests, repository validation, changelog and
whitespace checks before committing/pushing; inspect exact-head CI afterward.
