import XCTest

/// Real app controls and real ARSession only. No fixture depth, seeded progress,
/// forced orientation or changed confidence/freshness thresholds.
final class BenchUITests: XCTestCase {
    @MainActor func testCameraStopAndBackgroundRecovery() throws {
        try checkCameraStopAndBackgroundRecovery(requireRecordedTarget: false)
    }

    /// Requires an operator-positioned left target. A failed prerequisite is not
    /// evidence that a nonzero counter was cleared by backgrounding.
    @MainActor func testRecordedTargetResetsAfterBackground() throws {
        try checkCameraStopAndBackgroundRecovery(requireRecordedTarget: true)
    }

    @MainActor private func checkCameraStopAndBackgroundRecovery(requireRecordedTarget: Bool) throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        let toggle = app.buttons["cameraToggle"]
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10))
        // SwiftUI List creates lower rows lazily; reveal the real control.
        for _ in 0..<3 {
            if toggle.exists && toggle.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(toggle.waitForExistence(timeout: 5))
        defer {
            if app.state == .runningForeground && toggle.exists && toggle.label == "Stop camera" {
                if !toggle.isHittable { app.swipeUp() }
                if toggle.isHittable { toggle.tap() }
            }
        }
        guard toggle.isEnabled else { throw XCTSkip("Scene depth unsupported; no physical camera test.") }
        toggle.tap()
        // Permission is controlled by iOS/the operator, never silently granted.
        guard waitForMeasurement(app, timeout: 25) else {
            throw XCTSkip("No measured live depth. Hold phone portrait, rear camera unobstructed. No lifecycle acceptance claimed.")
        }
        for index in 0..<3 {
            print("BEFORE_STOP column=\(index) reading=\(app.staticTexts["distance\(index)"].label) detail=\(app.staticTexts["depthDetail\(index)"].label)")
        }
        toggle.tap()
        XCTAssertEqual(toggle.label, "Start portrait check")
        assertUnknown(app)
        XCTAssertTrue(app.staticTexts["mappingStatus"].label.hasPrefix("Stopped;"))

        toggle.tap()
        XCTAssertTrue(waitForMeasurement(app, timeout: 25), "Need new measured depth before background test")
        if requireRecordedTarget {
            // Operator places a real target on physical left; no seeded progress.
            let record = app.buttons["Record target on physical left"]
            reveal(record, in: app)
            XCTAssertTrue(record.waitForExistence(timeout: 5))
            XCTAssertTrue(record.isEnabled)
            // Wait for the existing app's separation requirement, without changing it.
            let separated = NSPredicate { _, _ in
                let values = (0..<3).compactMap { index -> Double? in
                    let label = app.staticTexts["distance\(index)"].label
                    guard label.hasSuffix(" m") else { return nil }
                    return label.split(separator: " ").dropLast().last.flatMap { Double($0) }
                }
                return values.count == 3 && values[0] + 0.2 <= values[1] && values[0] + 0.2 <= values[2]
            }
            XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: separated, object: app)], timeout: 30), .completed,
                           "Physical left target must be at least 0.2 m nearer than center/right; keep phone upright.")
            record.tap()
            let counts = app.staticTexts["mountCounts"]
            let nonzero = NSPredicate { _, _ in counts.label == "Left 1/3 · Center 0/3 · Right 0/3" }
            XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: nonzero, object: counts)], timeout: 5), .completed,
                           "Need a real recorded left target before background; no reset acceptance from zero counters.")
            print("BEFORE_BACKGROUND_COUNTS=\(counts.label)")
        }
        XCUIApplication(bundleIdentifier: "com.apple.springboard").activate()
        let background = NSPredicate { _, _ in
            let state = app.state
            print("AFTER_HOME_STATE=\(state.rawValue)")
            return state == .runningBackground || state == .runningBackgroundSuspended
        }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: background, object: app)], timeout: 10), .completed)
        app.activate()
        // Recovery must provide a new live measurement. Detailed source-age /
        // epoch fencing is exercised by core tests, not inferred from a UI label.
        XCTAssertTrue(waitForMeasurement(app, timeout: 25), "No live recovery after foreground")
        let counts = app.staticTexts["mountCounts"]
        reveal(counts, in: app)
        XCTAssertEqual(counts.label, "Left 0/3 · Center 0/3 · Right 0/3")
        XCTAssertTrue(app.buttons["Record target on physical left"].exists)
        print("AFTER_BACKGROUND_COUNTS=\(counts.label)")
        // Always leave the camera stopped after a successful automation run.
        reveal(toggle, in: app)
        toggle.tap()
        assertUnknown(app)
    }

    @MainActor private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<5 {
            if element.exists && element.isHittable { return }
            app.swipeUp()
        }
        for _ in 0..<5 {
            if element.exists && element.isHittable { return }
            app.swipeDown()
        }
    }

    @MainActor private func waitForMeasurement(_ app: XCUIApplication, timeout: TimeInterval) -> Bool {
        let predicate = NSPredicate { _, _ in
            (0..<3).contains { index in
                let reading = app.staticTexts["distance\(index)"]
                return reading.exists && reading.label.hasSuffix(" m")
            }
        }
        return XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: predicate, object: app)], timeout: timeout) == .completed
    }

    @MainActor private func assertUnknown(_ app: XCUIApplication) {
        for index in 0..<3 {
            XCTAssertTrue(app.staticTexts["distance\(index)"].label.hasSuffix("Unknown"))
        }
    }
}

/// Operator must stage the named real surface before selecting one test. Names
/// express the requested condition; UI automation cannot identify the material.
/// Outputs are UI snapshots, not synchronized sensor frames or accuracy trials.
final class SurfaceUITests: XCTestCase {
    @MainActor func testGlassObservation() throws { try observe("glass") }
    @MainActor func testDarkObjectObservation() throws { try observe("dark_object") }
    @MainActor func testIndoorGlareObservation() throws { try observe("indoor_glare") }
    @MainActor func testBlockedViewObservation() throws { try observe("blocked_view") }

    @MainActor private func observe(_ condition: String) throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        let toggle = app.buttons["cameraToggle"]
        reveal(toggle, in: app)
        XCTAssertTrue(toggle.waitForExistence(timeout: 10))
        guard toggle.isEnabled else { throw XCTSkip("Scene depth unsupported; no physical surface evidence.") }
        defer {
            if app.state == .runningForeground && toggle.exists && toggle.label == "Stop camera" {
                reveal(toggle, in: app)
                if toggle.isHittable { toggle.tap() }
            }
        }
        XCTAssertEqual(toggle.label, "Start portrait check")
        toggle.tap()
        XCTAssertEqual(toggle.label, "Stop camera")
        let start = ProcessInfo.processInfo.systemUptime
        // Each accessibility query is a separate UI read; do not infer that all
        // sectors came from one capture, or that successive reads are new frames.
        for sample in 0..<5 {
            let status = app.staticTexts["mappingStatus"]
            reveal(status, in: app)
            XCTAssertTrue(status.exists)
            for text in app.staticTexts.allElementsBoundByIndex {
                let wording = text.label.lowercased()
                XCTAssertFalse(["safe to cross", "all clear", "path clear", "go ahead"].contains(where: { wording.contains($0) }),
                               "Surface UI must not issue a permissive message")
            }
            var sectors: [[String: Any]] = []
            for column in 0..<3 {
                let reading = app.staticTexts["distance\(column)"]
                let detail = app.staticTexts["depthDetail\(column)"]
                XCTAssertTrue(reading.exists)
                XCTAssertTrue(detail.exists)
                let label = reading.label
                let unknown = label.hasSuffix("Unknown")
                var sector: [String: Any] = ["column": column, "reading": label,
                                             "detail": detail.label, "unknown": unknown]
                if unknown { sector["displayed_metres"] = NSNull() }
                else {
                    XCTAssertTrue(label.hasSuffix(" m"), "Unexpected reading: \(label)")
                    let value = try XCTUnwrap(label.split(separator: " ").dropLast().last.flatMap { Double($0) })
                    XCTAssertTrue(value.isFinite && value > 0, "Missing depth must not become zero/infinite distance")
                    sector["displayed_metres"] = value
                }
                sectors.append(sector)
            }
            let row: [String: Any] = ["requested_condition": condition, "ui_sample": sample,
                "elapsed_test_seconds": ProcessInfo.processInfo.systemUptime - start,
                "status": status.label, "sectors": sectors,
                "material_verified_by_automation": false, "capture_age_measured": false]
            let data = try JSONSerialization.data(withJSONObject: row, options: [.sortedKeys])
            print("CS020_SNAPSHOT " + String(decoding: data, as: UTF8.self))
        }
        reveal(toggle, in: app)
        toggle.tap()
        for column in 0..<3 {
            XCTAssertTrue(app.staticTexts["distance\(column)"].label.hasSuffix("Unknown"))
        }
        XCTAssertTrue(app.staticTexts["mappingStatus"].label.hasPrefix("Stopped;"))
    }

    @MainActor private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<5 {
            if element.exists && element.isHittable { return }
            app.swipeUp()
        }
        for _ in 0..<5 {
            if element.exists && element.isHittable { return }
            app.swipeDown()
        }
    }
}
