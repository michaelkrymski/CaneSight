import XCTest
import simd
import CaneSightDepth
import CaneSightPreviewState

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
