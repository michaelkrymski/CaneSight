import XCTest
import simd
@testable import CaneSightPreviewState

final class FloorSurfaceMaskTests: XCTestCase {
    let polygon:[SIMD2<Float>]=[[-2,-3],[2,-3],[2,0],[-2,0]]
    func plane() -> FloorSurfaceMask.Plane {
        var t=matrix_identity_float4x4
        t.columns.3.y=1 // camera is one metre above horizontal floor
        return .init(cameraToPlane:t,boundary:polygon)
    }
    func mask(_ depths:[Float], levels:[UInt8]?=nil, planes:[FloorSurfaceMask.Plane]?=nil) -> [Int] {
        FloorSurfaceMask.indices(width:1,height:depths.count,metres:depths,
            confidence:levels ?? Array(repeating:2,count:depths.count),intrinsics:[1,1,0,0],planes:planes ?? [plane()])
    }
    func testFloorRemovedButRaisedObstacleAndUnknownPixelsPreserved() {
        // y=1,z=1 reaches floor. z=.9 leaves point 10 cm above it.
        XCTAssertEqual(mask([1,1]),[1])
        XCTAssertEqual(mask([1,0.9]),[])
        XCTAssertEqual(mask([1,1],levels:[2,1]),[])
        XCTAssertEqual(mask([1,.nan]),[])
        XCTAssertEqual(mask([1,1],planes:[]),[])
    }
    func testBoundaryInsetAndOutsideRemainUnmasked() {
        XCTAssertTrue(FloorSurfaceMask.contains([0,-1],boundary:polygon))
        XCTAssertFalse(FloorSurfaceMask.contains([1.98,-1],boundary:polygon))
        XCTAssertFalse(FloorSurfaceMask.contains([3,-1],boundary:polygon))
        XCTAssertFalse(FloorSurfaceMask.contains([0,-1],boundary:[]))
    }
    func testRotatedCameraUsesPlaneTransformAndDoesNotMaskWall() {
        var t=matrix_identity_float4x4
        t.columns.0=[0,1,0,0];t.columns.1=[-1,0,0,0];t.columns.3.y=1
        // With phone roll, x=-1 maps onto floor rather than image bottom.
        let p=FloorSurfaceMask.Plane(cameraToPlane:t,boundary:polygon)
        let result=FloorSurfaceMask.indices(width:3,height:1,metres:[1,1,1],confidence:[2,2,2],
            intrinsics:[1,1,1,0],planes:[p])
        XCTAssertEqual(result,[0])
    }
    func testNonfiniteAndInvalidIntrinsicsFailWithoutMasking() {
        XCTAssertEqual(FloorSurfaceMask.indices(width:1,height:1,metres:[1],confidence:[2],
            intrinsics:[0,1,0,0],planes:[plane()]),[])
        var p=matrix_identity_float4x4;p.columns.0.x = .nan
        XCTAssertEqual(mask([1,1],planes:[.init(cameraToPlane:p,boundary:polygon)]),[])
    }
}
