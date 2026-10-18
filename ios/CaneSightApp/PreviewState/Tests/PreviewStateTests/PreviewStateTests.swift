import XCTest
import CaneSightPreviewState

final class PreviewStateTests: XCTestCase {
    func testInterruptionRejectsLateWorkerResultAndRecoveryRequiresNewEpoch() {
        var state = PreviewState<String>()
        let previous = state.epoch
        XCTAssertTrue(state.accept("before pause", epoch: previous, sourceSeconds: 1, receiptSeconds: 10, nowSeconds: 10))
        state.invalidate()
        XCTAssertNil(state.value)
        XCTAssertFalse(state.accept("late old frame", epoch: previous, sourceSeconds: 2, receiptSeconds: 11, nowSeconds: 11))
        XCTAssertTrue(state.accept("fresh session", epoch: state.epoch, sourceSeconds: 3, receiptSeconds: 12, nowSeconds: 12))
    }

    func testIdleTimeoutClearsAtBoundaryAndTicksCannotRenew() {
        var state = PreviewState<Int>()
        XCTAssertNil(state.value)
        XCTAssertTrue(state.accept(1, epoch: state.epoch, sourceSeconds: 7, receiptSeconds: 10, nowSeconds: 10))
        state.tick(nowSeconds: 10.499)
        XCTAssertEqual(state.value, 1)
        state.tick(nowSeconds: 10.5)
        XCTAssertNil(state.value)
        state.tick(nowSeconds: 11)
        XCTAssertNil(state.value)
    }

    func testDelayedMainQueueResultAndDuplicateCaptureCannotRestorePreview() {
        var state = PreviewState<Int>()
        XCTAssertFalse(state.accept(1, epoch: state.epoch, sourceSeconds: 1, receiptSeconds: 10, nowSeconds: 10.5))
        XCTAssertNil(state.value)
        XCTAssertTrue(state.accept(2, epoch: state.epoch, sourceSeconds: 2, receiptSeconds: 11, nowSeconds: 11))
        XCTAssertFalse(state.accept(3, epoch: state.epoch, sourceSeconds: 2, receiptSeconds: 11.1, nowSeconds: 11.1))
        XCTAssertNil(state.value)
    }

    func testClockReversalLatchesUnknownUntilExplicitInvalidation() {
        var state = PreviewState<Int>()
        XCTAssertTrue(state.accept(1, epoch: state.epoch, sourceSeconds: 1, receiptSeconds: 10, nowSeconds: 10))
        state.tick(nowSeconds: 9)
        XCTAssertNil(state.value)
        XCTAssertFalse(state.accept(2, epoch: state.epoch, sourceSeconds: 2, receiptSeconds: 11, nowSeconds: 11))
        state.invalidate()
        XCTAssertTrue(state.accept(3, epoch: state.epoch, sourceSeconds: 3, receiptSeconds: 12, nowSeconds: 12))
    }

    func testFutureReceiptAndNonfiniteSourceStayUnknown() {
        for source in [Double.nan, Double.infinity, -1] {
            var state = PreviewState<Int>()
            XCTAssertFalse(state.accept(1, epoch: state.epoch, sourceSeconds: source, receiptSeconds: 10, nowSeconds: 10))
            XCTAssertNil(state.value)
        }
        var state = PreviewState<Int>()
        XCTAssertFalse(state.accept(1, epoch: state.epoch, sourceSeconds: 1, receiptSeconds: 11, nowSeconds: 10))
        XCTAssertNil(state.value)
    }
}
