# CS-033 CI Compose fixture portability

Task/PR: CS-033, https://github.com/michaelkrymski/CaneSight/pull/93.
Branch: task/CS-033-backend-refresh. Prior head: 014f0a37595b8545292eac58453a6450513b24d3.
Accepted base: 5234f04135270eedcfd65f520fd179a49af40ab5.

CI repository-checks failed only the new application Compose config test; local
Compose v5 accepted the no-env-resolution invocation. Match existing portable
repository tests: copy all three Compose files into a temporary directory, create
synthetic native/application env files and an empty private-config mount directory,
then resolve normal config JSON without reading actual private files. Explicitly
assert both fixture settings survive the merge and neither reaches the proxy,
alongside existing resource/model/loopback assertions. Do not skip or weaken the
test, change runtime YAML or alter the protected workflow.

Three focused tests passed after this change. Checked publishing/shared and CI
follow-up are run on the resulting head. Initial packaging evidence records its
original test-source hash; this new handoff records the test-only follow-up.
Application image b9a4679 and all actual runtime/packaging source are unchanged;
no image rebuild, provider activation or physical acceptance follows.
