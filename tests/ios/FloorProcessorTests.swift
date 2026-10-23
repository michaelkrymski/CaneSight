import XCTest
import simd
import CaneSightDepth
@testable import CaneSightPreviewState

final class FloorProcessorTests: XCTestCase {
    func testFloorOnlySectorsBecomeUnknownAndRaisedRightObstacleRemainsMeasured() throws {
        let w=9,h=120
        var depths=[Float]()
        let levels=[UInt8](repeating:2,count:w*h)
        for y in 0..<h { for x in 0..<w {
            let floor=100/Float(y+100)
            depths.append(x>=6 ? floor*0.5 : floor)
        } }
        var cameraToFloor=matrix_identity_float4x4;cameraToFloor.columns.3.y=1
        let plane=FloorSurfaceMask.Plane(cameraToPlane:cameraToFloor,boundary:[[-2,-3],[2,-3],[2,0],[-2,0]])
        let mask=FloorSurfaceMask.indices(width:w,height:h,metres:depths,confidence:levels,
            intrinsics:[100,100,4,-100],planes:[plane])
        XCTAssertEqual(mask.count,6*h)
        for i in mask { depths[i] = .nan }
        let summary=DepthSectorProcessor(configuration:try DepthSectorConfiguration()).process(
            DepthFrame(width:w,height:h,metres:depths,confidence:levels,captureTimestampSeconds:1,mode:.live,tracking:.normal))
        XCTAssertNil(summary.sectors[0].distanceMetres)
        XCTAssertNil(summary.sectors[1].distanceMetres)
        XCTAssertEqual(summary.sectors[0].validFraction,0)
        XCTAssertEqual(summary.sectors[2].evidence,.measured)
        XCTAssertEqual(summary.sectors[2].validFraction,1)
        // Confidence remains unchanged and the full original denominator is retained.
        XCTAssertEqual(summary.sectors[2].totalSamples,360)
    }
}

final class TallMountRegionProcessorTests: XCTestCase {
    func testTallBandAboveTwoMetresHasNumericSummariesAndOriginalCaptureTime() throws {
        var selected=CalibratedMountGeometry.Selection()
        selected.metres=(0..<3).map { _ in Array(repeating:Float(2.7),count:6864) }
        selected.confidence=(0..<3).map { _ in Array(repeating:UInt8(2),count:6864) }
        // Exact former failure: a 6864-row single-pixel-column layout exceeds
        // the unchanged 2048 dimension limit despite valid 2.7 m samples.
        let legacy=DepthSectorProcessor(configuration:try DepthSectorConfiguration()).process(
            DepthFrame(width:3,height:6864,metres:Array(repeating:2.7,count:6864*3),
                confidence:Array(repeating:2,count:6864*3),captureTimestampSeconds:123.456,mode:.live,tracking:.normal))
        XCTAssertEqual(legacy.reason,.invalidDimensions)
        let packed=try XCTUnwrap(CalibratedMountGeometry.pack(selected))
        let summary=DepthSectorProcessor(configuration:try DepthSectorConfiguration()).process(
            DepthFrame(width:packed.width,height:packed.height,metres:packed.metres,confidence:packed.confidence,
                captureTimestampSeconds:123.456,mode:.live,tracking:.normal))
        XCTAssertEqual(summary.reason,.processedFrame)
        XCTAssertEqual(summary.captureTimestampSeconds,123.456)
        for sector in summary.sectors {
            XCTAssertEqual(sector.distanceMetres!,2.7,accuracy:0.00001)
            XCTAssertEqual(sector.validSamples,6864)
            XCTAssertGreaterThan(sector.validFraction!,0.99)
        }
    }
}
