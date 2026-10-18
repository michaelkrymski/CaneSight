import XCTest

/// Real controls/sensor only; no injected capture, progress, enrollment or consent.
final class HostUITests: XCTestCase {
    @MainActor func testOperatorLockAndFreshDepthRecovery() throws {
        guard ProcessInfo.processInfo.environment["CANESIGHT_OPERATOR_LOCK_TEST"] == "1" else {
            throw XCTSkip("Operator lock test requires explicit runner opt-in")
        }
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments += ["--depth-demo", "--lifecycle-probe"]
        app.launch()
        let toggle = app.buttons["demoCaptureToggle"]
        XCTAssertTrue(toggle.waitForExistence(timeout: 10))
        guard toggle.isEnabled else { throw XCTSkip("Real depth unsupported") }
        toggle.tap()
        let measured = NSPredicate { _,_ in
            (0..<3).contains { app.staticTexts["demoDistance\($0)"].label.contains(" m") }
        }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: measured, object: app)], timeout: 25), .completed)
        print("CS013_LOCK_CUE: operator locks for 20 seconds, unlocks and reopens CaneSight")
        let hidden = NSPredicate { _,_ in app.state == .runningBackground || app.state == .runningBackgroundSuspended }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: hidden, object: app)], timeout: 90), .completed)
        let foreground = NSPredicate { _,_ in app.state == .runningForeground }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: foreground, object: app)], timeout: 120), .completed)
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: measured, object: app)], timeout: 25), .completed)
        reveal(toggle, in: app); toggle.tap()
        for index in 0..<3 { XCTAssertEqual(app.staticTexts["demoResponse\(index)"].label, "Unknown") }
        print("CS013_LOCK_RECOVERY: real depth returned, Stop unknown; inspect on-device lifecycle proof counts separately")
    }

    @MainActor func testRealDepthDemoAndStop() throws {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments += ["--depth-demo"]
        app.launch()
        let toggle = app.buttons["demoCaptureToggle"]
        XCTAssertTrue(toggle.waitForExistence(timeout: 10))
        guard toggle.isEnabled else { throw XCTSkip("Real scene depth unsupported") }
        toggle.tap()
        let measured = NSPredicate { _,_ in
            (0..<3).contains { app.staticTexts["demoDistance\($0)"].label.contains(" m") }
        }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: measured, object: app)], timeout: 25), .completed)
        for index in 0..<3 {
            let response = app.staticTexts["demoResponse\(index)"]
            if !response.isHittable { app.swipeUp() }
            XCTAssertTrue(response.exists)
        }
        let live = XCTAttachment(screenshot: app.screenshot())
        live.name = "Real depth with visual simulated responses"
        live.lifetime = .keepAlways
        add(live)
        reveal(toggle, in: app); toggle.tap()
        for index in 0..<3 {
            let distance = app.staticTexts["demoDistance\(index)"]
            XCTAssertEqual(distance.label, "Unknown")
            XCTAssertEqual(app.staticTexts["demoResponse\(index)"].label, "Unknown")
        }
    }

    @MainActor func testLiveCameraStopAndBackground() throws {
        continueAfterFailure=false
        let app=XCUIApplication(); app.launch()
        app.tabBars.buttons["Status"].tap()
        let toggle=app.buttons["cs018.captureToggle"]
        XCTAssertTrue(toggle.waitForExistence(timeout: 10))
        guard toggle.isEnabled else { throw XCTSkip("Scene depth unsupported on this device") }
        defer {
            if app.state == .runningForeground && toggle.exists && toggle.label == "Stop camera" {
                reveal(toggle,in: app); if toggle.isHittable { toggle.tap() }
            }
        }
        reveal(toggle,in: app); toggle.tap()
        guard waitForMeasurement(app) else {
            throw XCTSkip("No real measured depth: hold portrait and keep rear cameras unobstructed. No physical pass inferred.")
        }
        reveal(toggle,in: app); toggle.tap()
        assertUnknown(app)
        XCTAssertEqual(toggle.label,"Start camera")
        toggle.tap()
        XCTAssertTrue(waitForMeasurement(app))
        XCUIApplication(bundleIdentifier: "com.apple.springboard").activate()
        let background=NSPredicate { _,_ in app.state == .runningBackground || app.state == .runningBackgroundSuspended }
        XCTAssertEqual(XCTWaiter.wait(for:[XCTNSPredicateExpectation(predicate:background,object:app)],timeout:10),.completed)
        app.activate()
        XCTAssertTrue(waitForMeasurement(app))
        reveal(toggle,in: app); toggle.tap(); assertUnknown(app)
    }

    @MainActor func testStatusReadAndCancel() {
        continueAfterFailure=false
        let app=XCUIApplication(); app.launch()
        app.tabBars.buttons["Status"].tap()
        let read=app.buttons["readStatus"]
        XCTAssertTrue(read.waitForExistence(timeout:10))
        XCTAssertGreaterThanOrEqual(read.frame.height,60)
        read.tap()
        let audio=row("cs018.audioStatus",in:app)
        let started=NSPredicate { _,_ in self.text(audio).contains("Narration requested") || self.text(audio).contains("Narration active") }
        XCTAssertEqual(XCTWaiter.wait(for:[XCTNSPredicateExpectation(predicate:started,object:audio)],timeout:10),.completed)
        let cancel=app.buttons["cs018.cancelAudio"]; reveal(cancel,in:app)
        XCTAssertTrue(cancel.isEnabled); XCTAssertGreaterThanOrEqual(cancel.frame.height,60)
        cancel.tap()
        XCTAssertTrue(text(audio).contains("cancellation requested"))
    }

    @MainActor func testLocalLocationConsentAndOptOut() {
        continueAfterFailure=false
        let app=XCUIApplication(); app.launch()
        app.tabBars.buttons["Location"].tap()
        let toggle=app.switches["locationConsent"]
        XCTAssertTrue(toggle.waitForExistence(timeout:10))
        XCTAssertEqual(toggle.value as? String,"0")
        toggle.coordinate(withNormalizedOffset: CGVector(dx:0.9,dy:0.5)).tap()
        // Michael authorized phone feature testing. Use the ordinary iOS
        // one-time permission prompt; never change global Settings or privacy.
        let system=XCUIApplication(bundleIdentifier:"com.apple.springboard")
        let once=system.buttons["Allow Once"]
        if once.waitForExistence(timeout:5) { once.tap() }
        let status=app.staticTexts["locationStatus"]
        XCTAssertTrue(status.waitForExistence(timeout:5))
        XCTAssertEqual(toggle.value as? String,"1")
        let available=NSPredicate { _,_ in status.label.contains("available locally") }
        let fixSeen=XCTWaiter.wait(for:[XCTNSPredicateExpectation(predicate:available,object:status)],timeout:10) == .completed
        print("LOCAL_GPS_FIX_AVAILABLE=\(fixSeen)")
        print("LOCAL_GPS_STATUS=\(status.label)") // Availability only; no coordinates.
        toggle.coordinate(withNormalizedOffset: CGVector(dx:0.9,dy:0.5)).tap()
        XCTAssertEqual(toggle.value as? String,"0")
        XCTAssertTrue(status.label.contains("Location off"))
        XCTAssertFalse(app.staticTexts["Fix age"].exists)
    }

#if targetEnvironment(simulator)
    @MainActor func testUnsupportedCameraShowsUnavailable() {
        let app=XCUIApplication(); app.launch()
        XCTAssertTrue(text(row("hardwareSupport",in:app)).contains("Unavailable"))
        app.tabBars.buttons["Status"].tap()
        XCTAssertFalse(app.buttons["cs018.captureToggle"].isEnabled)
        XCTAssertTrue(text(row("cs018.depthStatus",in:app)).contains("unsupported"))
    }
#endif

    @MainActor func testLocationDefaultsOff() {
        let app=XCUIApplication(); app.launch()
        app.tabBars.buttons["Location"].tap()
        let toggle=app.switches["locationConsent"]
        XCTAssertTrue(toggle.waitForExistence(timeout:10))
        XCTAssertEqual(toggle.value as? String,"0")
        XCTAssertTrue(app.staticTexts["locationStatus"].label.contains("Location off"))
        // Do not grant system location permission or opt into collection here.
    }

    @MainActor func testLargestTextControlsAndLabels() {
        let app=XCUIApplication()
        app.launchArguments += ["-UIPreferredContentSizeCategoryName","UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch(); app.tabBars.buttons["Status"].tap()
        let read=app.buttons["readStatus"]; XCTAssertTrue(read.waitForExistence(timeout:10))
        XCTAssertTrue(read.isHittable); XCTAssertGreaterThanOrEqual(read.frame.height,60)
        let cancel=app.buttons["cs018.cancelAudio"]; reveal(cancel,in:app)
        XCTAssertTrue(cancel.isHittable); XCTAssertGreaterThanOrEqual(cancel.frame.height,60)
        XCTAssertEqual(cancel.label,"Cancel audio")
        XCTAssertTrue(row("cs018.connectionStatus",in:app).exists)
    }

    @MainActor private func row(_ id:String,in app:XCUIApplication)->XCUIElement {
        app.descendants(matching:.any).matching(identifier:id).firstMatch
    }
    @MainActor private func text(_ element:XCUIElement)->String {
        element.label+" "+(element.value as? String ?? "")
    }
    @MainActor private func reveal(_ element:XCUIElement,in app:XCUIApplication) {
        if element.exists && element.isHittable { return }
        for _ in 0..<5 { app.swipeUp(); if element.exists && element.isHittable { return } }
        for _ in 0..<5 { app.swipeDown(); if element.exists && element.isHittable { return } }
    }
    @MainActor private func waitForMeasurement(_ app:XCUIApplication)->Bool {
        let measured=NSPredicate { _,_ in
            (0..<3).contains { self.text(self.row("cs018.sector.\($0)",in:app)).contains("metres") }
        }
        return XCTWaiter.wait(for:[XCTNSPredicateExpectation(predicate:measured,object:app)],timeout:25) == .completed
    }
    @MainActor private func assertUnknown(_ app:XCUIApplication) {
        for i in 0..<3 { XCTAssertTrue(text(row("cs018.sector.\(i)",in:app)).contains("Unknown")) }
    }
}
