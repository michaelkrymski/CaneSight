# CS-035 Compose CI portability - 2026-10-17

Owner: Gavin (`gmarcialcalleja`). Branch: task/CS-035-observation-results.
Base: 9486d8eeb04e5ad733cfa0bb47ff017bd99cead4. PR #28.

GitHub Linux CI exposed an older Compose JSON serializer omitting the explicit
false create_host_path value. Confirmed upstream compose-go PR #836:
https://github.com/compose-spec/compose-go/pull/836

Change only the test assertion: require the source overlay's explicit false
setting and reject a true normalized value while accepting omitted false.
The deployment overlay and runtime remain unchanged; no protection weakened.

Validation: all 13 focused native tests passed in the Windows pinned environment,
including actual-model HTTPS/WSS. Checked publishing reruns all 39 shared tests,
repository, changelog and whitespace checks. New head CI must pass separately.
No new model/performance/deployment or hardware claim; candidate evidence from
handoffs/CS-035-20261017-native-result-integration.md remains applicable.
