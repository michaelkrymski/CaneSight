import XCTest
import CaneSightDepth

/// Synthetic explanation tests using the unchanged production processor.
/// These are counterexamples, not measurements of the mounted chair.
final class PortraitTargetTests: XCTestCase {
    func rightChair(highConfidenceNear: Int) -> DepthSectorSummary {
        let width=9, height=120
        var metres=[Float](repeating:3,count:width*height)
        var confidence=[UInt8](repeating:2,count:width*height)
        var rightIndex=0
        for y in 0..<height { for x in 6..<9 {
            let offset=y*width+x
            // 230 near but low-confidence samples; 130 retained samples total.
            metres[offset]=0.8; confidence[offset]=0
            if rightIndex<130 {
                confidence[offset]=2; metres[offset]=rightIndex<highConfidenceNear ? 0.8 : 3
            }
            rightIndex += 1
        } }
        return DepthSectorProcessor(configuration:try! DepthSectorConfiguration()).process(
            DepthFrame(width:width,height:height,metres:metres,confidence:confidence,
                captureTimestampSeconds:1,mode:.live,tracking:.normal))
    }
    func testNearChairCanBeExcludedWhileHighConfidenceBackgroundKeepsSectorNumeric() {
        let right=rightChair(highConfidenceNear:0).sectors[2]
        XCTAssertEqual(right.evidence,.measured)
        XCTAssertEqual(right.validSamples,130)
        XCTAssertEqual(right.totalSamples,360)
        XCTAssertEqual(right.validFraction!,130.0/360,accuracy:0.000001)
        XCTAssertEqual(right.distanceMetres,3)
        // Numeric global coverage says nothing about target-specific retention.
    }
    func testNearSamplesMustReachTenthPercentileOfRetainedPixels() {
        XCTAssertEqual(rightChair(highConfidenceNear:12).sectors[2].distanceMetres,3)
        XCTAssertEqual(rightChair(highConfidenceNear:13).sectors[2].distanceMetres!,0.8,accuracy:0.000001)
    }
}
