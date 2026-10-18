import XCTest

/// Real app controls and real ARSession only. No fixture depth, seeded progress,
/// forced orientation or changed confidence/freshness thresholds.
final class BenchUITests: XCTestCase {
    @MainActor func testCameraStopAndBackgroundRecovery() throws {
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
        // Always leave the camera stopped after a successful automation run.
        if !toggle.isHittable { app.swipeUp() }
        toggle.tap()
        assertUnknown(app)
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
