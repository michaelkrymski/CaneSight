# CS-020 challenging-surface observations

Use the existing Mount Check bench on a physical supported iPhone. Select one
`SurfaceUITests` method at a time after the operator stages the named condition:
`testGlassObservation`, `testDarkObjectObservation`, `testIndoorGlareObservation`
or `testBlockedViewObservation`. Never run all four on one unchanged scene and
call them four material trials. A method name does not establish material identity.

Hold the phone portrait upright, rear sensors forward, stationary indoors.
For glass/dark/glare, place the named material across a substantial portion of
one or more preview columns about 0.5–1 m away, with farther background. Record
which material and columns the operator actually covered, approximate versus
measured distance, indoor illumination and any visible glare. A shiny object
without visible glare is a reflective-surface trial, not a verified glare trial.
For the blocked-view test, hold an opaque card in front of the entire rear camera
and LiDAR cluster. Material very close to the sensors may itself return depth;
blocking the view does not guarantee the sensor will produce no depth.

The test starts normal capture, records five UI snapshots (status, displayed
metres or Unknown and existing coverage explanations), then stops and checks all
readings are Unknown. Snapshot fields are queried sequentially: they are not
synchronized frames or independent captures, and may repeat data. Elapsed test
time is not capture age or sensor latency. UI test success means these controls
and representations behaved as asserted, not that the material was detected.

Interpretation:
- A numerical reading may be background, floor, the material, a reflection or
  another surface. It does not prove an obstacle is absent or that glass was seen.
- Unknown stays Unknown. Confidence/coverage filtering and the near percentile
  stay unchanged. Never replace missing/low-confidence depth with a clear-path
  state. Sensor quality can vary across columns and time.
- Log unexpected finite readings and mixed Unknown/measured states, including
  failures. Missing materials, missing glare, skipped tests or unstaged conditions
  remain untested, rather than passed. Stop-to-Unknown is a separate UI check.

Prepare exact review inputs with `ios/MappingBench/prepare_review_dependencies.py`.
Use Xcode MountCheck scheme with local signing and the paired device, selecting
only the staged test. In terminal, use `xcodebuild test` or build-for-testing plus
test-without-building with `-only-testing:MountCheckUITests/SurfaceUITests/<method>`.
Keep derived data, logs, screenshots and xcresult bundles outside Git: XCTest
attachments may contain private camera views. Only explicitly reviewed sanitized
`CS020_SNAPSHOT` JSON rows and material/operator notes belong in evidence records.
Do not store unique device identifiers, signing information, photos or GPS.

The bench uses the exact depth package pin in its ReviewDependencies.json. Check
that manifest when interpreting results; do not claim another current host or
package was tested. This is local sensor preparation. CS-015 mapping and CS-017
integrated recovery dependencies, final mount, source-clock freshness, paired
phone/Pi transport, motor behavior and accuracy measurements remain separate.
No road-use or electrical acceptance is established by these checks.
