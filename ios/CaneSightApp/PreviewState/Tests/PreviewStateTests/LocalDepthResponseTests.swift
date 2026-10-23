import XCTest
import CaneSightPreviewState

final class LocalDepthResponseTests: XCTestCase {
    func testThresholdAndUnknownNeverMeanClear() {
        XCTAssertEqual(LocalDepthResponse(distanceMetres: 0.5), .near)
        XCTAssertEqual(LocalDepthResponse(distanceMetres: 1.2), .near)
        XCTAssertEqual(LocalDepthResponse(distanceMetres: 1.201), .aboveThreshold)
        for value in [nil, Double.nan, Double.infinity, -1, 0] {
            XCTAssertEqual(LocalDepthResponse(distanceMetres: value), .unknown)
        }
    }
    func testIndependentColumnsAndPreviewInvalidationRemoveResponse() {
        var preview = PreviewState<[Double?]>()
        XCTAssertTrue(preview.accept([0.7, 2, nil], epoch: preview.epoch,
            sourceSeconds: 1, receiptSeconds: 5, nowSeconds: 5))
        XCTAssertEqual(preview.value!.map { LocalDepthResponse(distanceMetres: $0) }, [.near, .aboveThreshold, .unknown])
        preview.tick(nowSeconds: 5.5)
        XCTAssertNil(preview.value)
        XCTAssertEqual(LocalDepthResponse(distanceMetres: preview.value?.first ?? nil), .unknown)
    }
}
