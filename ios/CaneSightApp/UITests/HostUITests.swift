import XCTest

/// Real controls/sensor only; no injected capture, progress, enrollment or consent.
final class HostUITests: XCTestCase {
    @MainActor func testExistingPhoneBondNativePairing() throws {
        #if !CS013_NATIVE_PAIRING_BENCH
        throw XCTSkip("Explicit local native-pairing bench build required; never authenticate from routine tests")
        #else
        continueAfterFailure = false
        let app = XCUIApplication(); app.launch()
        app.tabBars.buttons["Connection"].tap()
        let connect = app.buttons["phoneConnect"]
        XCTAssertTrue(connect.waitForExistence(timeout: 10))
        connect.tap()
        let status = app.staticTexts["connectionStatus"]
        let paired = NSPredicate { _, _ in status.label.contains("WSS connected") }
        let result = XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: paired, object: status)], timeout: 40)
        print("CS013_PHONE_PAIRING_STATUS " + status.label)
        XCTAssertEqual(result, .completed, "Phone status: " + status.label)
        XCTAssertTrue(status.label.contains("depth sends: 0"))
        #if CS013_NATIVE_DEPTH_BENCH
        // Operator explicitly authorized this stationary diagnostic transport run.
        app.tabBars.buttons["Camera"].tap()
        let camera = app.buttons["captureToggle"]
        XCTAssertTrue(camera.waitForExistence(timeout: 10)); camera.tap()
        app.tabBars.buttons["Connection"].tap()
        let disarmed = app.switches["diagnosticConsentConfirmation"]
        disarmed.switches.firstMatch.exists ? disarmed.switches.firstMatch.tap() : disarmed.tap()
        let diagnostic = app.switches["diagnosticDepth"]
        diagnostic.switches.firstMatch.exists ? diagnostic.switches.firstMatch.tap() : diagnostic.tap()
        let depthSent = NSPredicate { _, _ in
            let label = status.label
            guard label.contains("WSS connected"), let count = UInt64(label.components(separatedBy: "depth sends: ").last ?? "") else { return false }
            return count >= 10
        }
        let depthResult = XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: depthSent, object: status)], timeout: 35)
        print("CS013_PHONE_DIAGNOSTIC_DEPTH_STATUS " + status.label)
        XCTAssertEqual(depthResult, .completed, "Phone status: " + status.label)
        diagnostic.switches.firstMatch.exists ? diagnostic.switches.firstMatch.tap() : diagnostic.tap()
        #endif
        // Real OS foreground/background with the native bond controller. No
        // claim about receiver expiration, sensor drift, or physical guidance.
        XCUIApplication(bundleIdentifier: "com.apple.springboard").activate()
        app.activate()
        app.tabBars.buttons["Connection"].tap()
        let recovered = XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: paired, object: status)], timeout: 40)
        print("CS013_PHONE_PAIRING_RECOVERY " + status.label)
        XCTAssertEqual(recovered, .completed, "Phone status: " + status.label)
        XCTAssertEqual(app.switches["diagnosticConsentConfirmation"].value as? String, "0")
        XCTAssertEqual(app.switches["diagnosticDepth"].value as? String, "0")
        XCTAssertTrue(status.label.contains("depth sends: 0"))
        #endif
    }

    @MainActor func testPhonePairingMissingBondFailsClosed() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); app.launch()
        app.tabBars.buttons["Connection"].tap()
        let connect = app.buttons["phoneConnect"]
        XCTAssertTrue(connect.waitForExistence(timeout: 10))
        reveal(connect, in: app)
        // Existing real credentials must never be replaced or removed by a test.
        let status = app.staticTexts["connectionStatus"]
        guard status.label.contains("no phone bond") else {
            throw XCTSkip("Existing phone bond present; no authentication or credential mutation from this UI test")
        }
        let diagnostic = app.switches["diagnosticDepth"]
        XCTAssertFalse(diagnostic.isEnabled)
        connect.tap()
        XCTAssertEqual(status.label, "Existing private phone-bond.json is missing; import it first")
        XCTAssertEqual(connect.label, "Connect")
        XCTAssertFalse(diagnostic.isEnabled)
    }

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
    @MainActor func testMountSetupCannotSaveWithoutRealMeasurements() {
        let app=XCUIApplication();app.launch()
        let calibrate=app.buttons["calibrateMount"];reveal(calibrate,in:app)
        XCTAssertTrue(calibrate.waitForExistence(timeout:10));calibrate.tap()
        let capture=app.buttons["captureNeutralMount"];reveal(capture,in:app)
        XCTAssertTrue(capture.exists);XCTAssertFalse(capture.isEnabled)
        let helper=app.switches["mountHelperPresent"];reveal(helper,in:app)
        helper.coordinate(withNormalizedOffset:CGVector(dx:0.9,dy:0.5)).tap()
        reveal(capture,in:app);XCTAssertTrue(capture.isEnabled);capture.tap()
        XCTAssertFalse(app.buttons["saveMountCalibration"].exists)
        let status=app.staticTexts["mountCalibrationStatus"];reveal(status,in:app)
        XCTAssertTrue(status.waitForExistence(timeout:5))
        XCTAssertTrue(status.label.contains("fresh depth"))
        let moved=app.buttons["mountMoved"];reveal(moved,in:app);moved.tap()
        let profile=app.staticTexts["mountProfileStatus"];reveal(profile,in:app)
        XCTAssertTrue(profile.label.contains("required"))
        for i in 0..<3 {
            let distance=app.staticTexts["distance\(i)"];reveal(distance,in:app)
            XCTAssertEqual(distance.label.split(separator:",").last?.trimmingCharacters(in:.whitespaces),"Unknown")
        }
    }
    @MainActor func testMountInvalidationStaysRequiredAcrossBackgroundAndRelaunch() {
        let app=XCUIApplication();app.launch()
        let moved=app.buttons["mountMoved"];reveal(moved,in:app)
        XCTAssertTrue(moved.waitForExistence(timeout:10));moved.tap()
        XCUIApplication(bundleIdentifier:"com.apple.springboard").activate();app.activate()
        let status=app.staticTexts["mountProfileStatus"];reveal(status,in:app)
        XCTAssertTrue(status.label.contains("required"))
        app.terminate();app.launch();reveal(status,in:app)
        XCTAssertTrue(status.label.contains("required"))
        XCTAssertFalse(app.buttons["saveMountCalibration"].exists)
    }
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
        for _ in 0..<8 {
            app.coordinate(withNormalizedOffset:CGVector(dx:0.04,dy:0.8)).press(forDuration:0.05,
                thenDragTo:app.coordinate(withNormalizedOffset:CGVector(dx:0.04,dy:0.25)))
            if element.exists && element.isHittable { return }
        }
        for _ in 0..<8 {
            app.coordinate(withNormalizedOffset:CGVector(dx:0.04,dy:0.25)).press(forDuration:0.05,
                thenDragTo:app.coordinate(withNormalizedOffset:CGVector(dx:0.04,dy:0.8)))
            if element.exists && element.isHittable { return }
        }
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
