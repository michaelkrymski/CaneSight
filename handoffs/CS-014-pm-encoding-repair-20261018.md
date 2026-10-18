# CS-014: restore accepted metadata encoding

PR #62 repair, requested by Michael. Branch: task/CS-014-depth-sectors.
Starting head: 1f25eb138e2d6e862bc65645cc6eba67ceb4dd66.
Accepted main/base: 185aa3afaca1bdd6ba5380ba0e7113917f86b2df.

The task elapsed_window was accidentally mojibake-encoded instead of the accepted
2–5 value. Since it is outside runtime_fields, governance treated it as a plan
change requiring a CR and exact-head approval. Restore the exact accepted value;
no plan amendment or weakened check is needed. All static fields now match main.
The Swift implementation, tests, package and replay fixtures are unchanged.

Validation: all eight normalized readiness source hashes match; seven fixture
structures pass. Shared suite: 195 cases, 188 passed and seven platform skips,
no failures/errors. Structure, generated log and whitespace checks run before push.
The optional grammar audit could not run because tree_sitter is not installed;
no Swift/Apple/device test was rerun in this repair. Accepted #69 evidence remains
attributed as documented in the readiness report. Physical accuracy, mapping,
clock/transport and haptics remain separate gates. Review is not Done.
