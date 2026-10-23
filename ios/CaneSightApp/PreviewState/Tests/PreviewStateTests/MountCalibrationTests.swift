import XCTest
import simd
@testable import CaneSightPreviewState

final class MountCalibrationTests: XCTestCase {
    let identity=matrix_identity_float3x3
    func rotation(_ axis: SIMD3<Float>,_ degrees: Float) -> simd_float3x3 {
        simd_float3x3(simd_quatf(angle:degrees * .pi/180,axis:axis))
    }
    var neutral: simd_float3x3 { rotation([0,0,1],-90) }
    var camera: MountCamera { .init(device:"fixture",imageWidth:1920,imageHeight:1440,depthWidth:256,depthHeight:192,
        k:[0.8,0.8,0.5,0.5],display:[0,1,-4/3,0,7/6,0]) }
    func profile(_ region: MountRegion=MountRegion(y:3/8)) -> MountProfile {
        .init(camera:camera,region:region,neutral:neutral,cameraHeight:1)
    }
    func confirmed() -> MountProfile {
        var p=profile();p.helperConfirmed=true;p.verifiedSides=[true,true,true];p.lowObstacleVerified=true;return p
    }
    func testFullWidthBandHasThreeThirdsAndExplicitHeight() throws {
        XCTAssertEqual(MountRegion.width*180,180,accuracy:0.00001)
        XCTAssertEqual(MountRegion.defaultHeight*320,40,accuracy:0.00001)
        let p=profile(),polygons=try CalibratedMountGeometry.projection(p,camera:camera,pose:neutral)
        XCTAssertEqual(polygons[0][0].x,p.region.x,accuracy:0.00001)
        XCTAssertEqual(polygons[2][1].x,p.region.x+MountRegion.width,accuracy:0.00001)
        XCTAssertEqual(polygons[0][2].y,p.region.y+p.region.height,accuracy:0.00001)
        XCTAssertEqual(polygons[0][1].x,polygons[1][0].x,accuracy:0.000001)
    }
    func testPositiveNegativePitchAndRollProjectSamePhysicalRays() throws {
        let p=profile()
        for axis: SIMD3<Float> in [[1,0,0],[0,0,1]] {
            for angle: Float in [-8,8] {
                let pose=rotation(axis,angle)*neutral
                try CalibratedMountGeometry.validate(p,camera:camera,pose:pose,height:1)
                let projected=try CalibratedMountGeometry.projection(p,camera:camera,pose:pose)
                let ref=camera.ray([p.region.x,p.region.y])
                let actual=camera.ray(projected[0][0])
                let a=simd_normalize(pose*actual),b=simd_normalize(neutral*ref)
                XCTAssertLessThan(simd_length(a-b),0.00001)
            }
        }
    }
    func testWorldYawTurnsDoNotSwapCaneLeftRight() throws {
        for yaw: Float in [-170,-90,0,90,170] {
            let current=rotation([0,1,0],yaw)*neutral
            let level=try XCTUnwrap(CalibratedMountGeometry.cameraToLevel(current))
            for c in 0..<3 { XCTAssertLessThan(simd_length(level[c]-neutral[c]),0.00001) }
            let polygons=try CalibratedMountGeometry.projection(profile(),camera:camera,pose:level)
            XCTAssertLessThan(polygons[0][0].x,polygons[2][0].x)
        }
    }
    func testBoundsHeightAndUnsupportedPoseFailUnavailable() {
        let p=profile()
        XCTAssertThrowsError(try CalibratedMountGeometry.validate(p,camera:camera,pose:rotation([1,0,0],20)*neutral,height:1))
        XCTAssertThrowsError(try CalibratedMountGeometry.validate(p,camera:camera,pose:rotation([0,0,1],15)*neutral,height:1))
        XCTAssertThrowsError(try CalibratedMountGeometry.validate(p,camera:camera,pose:neutral,height:1.2))
        XCTAssertThrowsError(try CalibratedMountGeometry.validate(p,camera:camera,pose:neutral,height:nil))
        XCTAssertNil(CalibratedMountGeometry.cameraToLevel(rotation([1,0,0],90)))
        let edge=profile(MountRegion(y:0))
        XCTAssertThrowsError(try CalibratedMountGeometry.validate(edge,camera:camera,pose:rotation([1,0,0],-15)*neutral,height:1))
    }
    func testOriginalDepthPixelsSelectedOnceAndSectorOrderIsPhysical() throws {
        let p=profile(),n=camera.depthWidth*camera.depthHeight
        let selected=CalibratedMountGeometry.select(profile:p,camera:camera,pose:neutral,
            metres:Array(repeating:1,count:n),confidence:Array(repeating:2,count:n),floorIndices:[],height:1)
        XCTAssertTrue(selected.metres.allSatisfy { $0.count>=32 })
        XCTAssertLessThan(selected.metres.reduce(0) { $0+$1.count },n)
        // Independent raw-raster oracle for neutral transform: portrait X falls
        // with source Y, and its three narrow strips have disjoint row ranges.
        var expected=[0,0,0]
        for y in 0..<camera.depthHeight { for x in 0..<camera.depthWidth {
            let u=7.0/6.0-4.0/3.0*Double(y)/Double(camera.depthHeight)
            let v=Double(x)/Double(camera.depthWidth)
            if u>=Double(p.region.x),u<Double(p.region.x+MountRegion.width),
               v>=Double(p.region.y),v<Double(p.region.y+p.region.height) {
                let s=min(2,Int((u-Double(p.region.x))/Double(MountRegion.width)*3));expected[s]+=1
            }
        } }
        XCTAssertEqual(selected.metres.map(\.count),expected)
    }
    func testFloorAndLowConfidenceDoNotProduceFabricatedDistance() {
        let p=profile(),n=camera.depthWidth*camera.depthHeight
        let selected=CalibratedMountGeometry.select(profile:p,camera:camera,pose:neutral,
            metres:Array(repeating:1,count:n),confidence:Array(repeating:0,count:n),floorIndices:Set(0..<n),height:1)
        XCTAssertTrue(selected.metres.flatMap { $0 }.allSatisfy { $0.isNaN })
        XCTAssertTrue(selected.confidence.flatMap { $0 }.allSatisfy { $0==0 })
    }
    func testLowObstacleAboveFloorSlabRemainsInActualSelectedRegion() {
        // Fixture has downward-facing neutral camera and a target plane 10 cm
        // above known level floor. Its raw samples remain high confidence.
        let down=rotation([1,0,0],-35)*neutral
        let p=MountProfile(camera:camera,region:MountRegion(y:3/8),neutral:down,cameraHeight:1)
        var depths=[Float](),levels=[UInt8]()
        for y in 0..<camera.depthHeight { for x in 0..<camera.depthWidth {
            let ray=SIMD3<Float>((Float(x)/Float(camera.depthWidth)-camera.k[2])/camera.k[0],
                -(Float(y)/Float(camera.depthHeight)-camera.k[3])/camera.k[1],-1)
            let vertical=(down*ray).y
            depths.append(vertical < -0.01 ? -0.9/vertical : .nan);levels.append(2)
        } }
        var world=matrix_identity_float4x4
        world.columns.0=SIMD4(down.columns.0,0);world.columns.1=SIMD4(down.columns.1,0)
        world.columns.2=SIMD4(down.columns.2,0);world.columns.3=[0,1,0,1]
        let floor=FloorSurfaceMask.Plane(cameraToPlane:world,boundary:[[-8,-8],[8,-8],[8,0],[-8,0]])
        let mask=FloorSurfaceMask.indices(width:camera.depthWidth,height:camera.depthHeight,metres:depths,
            confidence:levels,intrinsics:[camera.k[0]*256,camera.k[1]*192,camera.k[2]*256,camera.k[3]*192],planes:[floor])
        XCTAssertTrue(mask.isEmpty)
        let selected=CalibratedMountGeometry.select(profile:p,camera:camera,pose:down,metres:depths,
            confidence:levels,floorIndices:Set(mask),height:1)
        XCTAssertGreaterThanOrEqual(selected.lowObstacleHighPixels,32)
        XCTAssertTrue(selected.metres.allSatisfy { $0.filter { $0.isFinite }.count>=32 })
    }
    func testOffscreenPartsOfWideBandStayUnknownWhileVisibleSectorCompensates() throws {
        let p=profile(),pose=rotation([0,0,1],8)*neutral
        let visible=try CalibratedMountGeometry.visibility(p,camera:camera,pose:pose)
        XCTAssertTrue(visible.contains(false));XCTAssertTrue(visible.contains(true))
        let n=camera.depthWidth*camera.depthHeight
        let result=CalibratedMountGeometry.select(profile:p,camera:camera,pose:pose,
            metres:Array(repeating:1,count:n),confidence:Array(repeating:2,count:n),floorIndices:[],height:1)
        let fractions=try CalibratedMountGeometry.visibleFractions(p,camera:camera,pose:pose)
        for sector in 0..<3 {
            if fractions[sector]>=CalibratedMountGeometry.minimumVisibleFraction {
                XCTAssertTrue(result.metres[sector].contains { $0.isFinite })
            } else { XCTAssertTrue(result.metres[sector].allSatisfy { $0.isNaN }) }
            if fractions[sector]<0.999 {
                XCTAssertGreaterThan(result.quality[sector]["offscreen_unknown_padding"] ?? 0,0)
            }
        }
    }
    func testTinyTiltKeepsSideMeasurementsAndPadsUnseenPixelsUnknown() throws {
        let p=profile(MountRegion(y:0.2372,height:0.5568))
        let pose=rotation([0,0,1],1)*neutral
        let fractions=try CalibratedMountGeometry.visibleFractions(p,camera:camera,pose:pose)
        XCTAssertTrue(fractions.allSatisfy { $0>=0.90 })
        XCTAssertTrue(fractions.contains { $0<0.999 })
        let n=camera.depthWidth*camera.depthHeight
        let result=CalibratedMountGeometry.select(profile:p,camera:camera,pose:pose,
            metres:Array(repeating:1,count:n),confidence:Array(repeating:2,count:n),floorIndices:[],height:1)
        for sector in 0..<3 {
            XCTAssertGreaterThan(result.metres[sector].filter { $0.isFinite }.count,32)
            let missing=result.quality[sector]["offscreen_unknown_padding"] ?? 0
            if missing>0 {
                XCTAssertTrue(result.metres[sector].suffix(missing).allSatisfy { $0.isNaN })
                XCTAssertTrue(result.confidence[sector].suffix(missing).allSatisfy { $0==0 })
            }
        }
    }
    func testSubstantialOffscreenLossKeepsAffectedSectorsEntirelyUnknown() throws {
        let p=profile(MountRegion(y:0,height:1)),pose=rotation([0,0,1],30)*neutral
        let fractions=try CalibratedMountGeometry.visibleFractions(p,camera:camera,pose:pose)
        XCTAssertTrue(fractions.contains { $0<CalibratedMountGeometry.minimumVisibleFraction })
        let n=camera.depthWidth*camera.depthHeight
        let result=CalibratedMountGeometry.select(profile:p,camera:camera,pose:pose,
            metres:Array(repeating:1,count:n),confidence:Array(repeating:2,count:n),floorIndices:[],height:1)
        for sector in 0..<3 where fractions[sector]<CalibratedMountGeometry.minimumVisibleFraction {
            XCTAssertTrue(result.metres[sector].allSatisfy { $0.isNaN })
            XCTAssertTrue(result.confidence[sector].allSatisfy { $0==0 })
        }
    }
    func testBandHeightChangesAreExplicitAndPositionIsClamped() {
        let band=MountRegion(y:0.9,height:0.5)
        XCTAssertEqual(band.height,0.5);XCTAssertEqual(band.y,0.5)
        XCTAssertEqual(band.x,0);XCTAssertEqual(MountRegion.width,1)
        XCTAssertTrue(band.valid)
    }
    func testBadDepthIsKeptUnknownInDenominatorAndOffRangeDoesNotCreateValues() {
        let p=profile(),n=camera.depthWidth*camera.depthHeight
        for value: Float in [.nan,0,-1,Float.infinity,10] {
            let result=CalibratedMountGeometry.select(profile:p,camera:camera,pose:neutral,
                metres:Array(repeating:value,count:n),confidence:Array(repeating:2,count:n),floorIndices:[],height:1)
            XCTAssertTrue(result.metres.allSatisfy { !$0.isEmpty })
            XCTAssertTrue(result.metres.flatMap { $0 }.allSatisfy { $0.isNaN })
        }
    }
    func testDepthAboveTwoMetresIsRetainedWithoutLoweringConfidencePolicy() {
        let p=profile(),n=camera.depthWidth*camera.depthHeight
        for level: UInt8 in [1,2] {
            let result=CalibratedMountGeometry.select(profile:p,camera:camera,pose:neutral,
                metres:Array(repeating:2.5,count:n),confidence:Array(repeating:level,count:n),floorIndices:[],height:1)
            for sector in 0..<3 {
                XCTAssertTrue(result.metres[sector].contains { $0>2 && $0<4 })
                XCTAssertTrue(result.confidence[sector].allSatisfy { $0==level })
                XCTAssertGreaterThan(result.quality[sector]["over_2m_raw"] ?? 0,32)
                if level==1 { XCTAssertEqual(result.quality[sector]["over_2m_high"] ?? 0,0) }
                else { XCTAssertGreaterThan(result.quality[sector]["over_2m_high"] ?? 0,32) }
            }
        }
    }
    func testHelperTargetDoesNotTreatUnknownBackgroundAsClearOrKnownTarget() {
        XCTAssertTrue(MountTargetEvidence.canRecord(target:0,distances:[0.8,nil,nil]))
        XCTAssertTrue(MountTargetEvidence.canRecord(target:1,distances:[nil,0.8,2.7]))
        XCTAssertFalse(MountTargetEvidence.canRecord(target:0,distances:[nil,0.8,2.7]))
        XCTAssertFalse(MountTargetEvidence.canRecord(target:0,distances:[0.8,0.7,nil]))
        XCTAssertFalse(MountTargetEvidence.canRecord(target:2,distances:[nil,nil,.nan]))
    }
    func testTallFullBandPackingStaysWithinDimensionsAndPreservesEachSectorExactlyOnce() throws {
        var s=CalibratedMountGeometry.Selection()
        for sector in 0..<3 {
            s.metres[sector]=(0..<(6864+sector*13)).map { Float(sector*10000+$0+1) }
            s.confidence[sector]=Array(repeating:2,count:s.metres[sector].count)
        }
        let packed=try XCTUnwrap(CalibratedMountGeometry.pack(s))
        XCTAssertLessThanOrEqual(packed.width,2048);XCTAssertLessThanOrEqual(packed.height,2048)
        XCTAssertLessThanOrEqual(packed.metres.count,262144)
        let stride=packed.width/3
        for sector in 0..<3 {
            var recovered=[Float]()
            for y in 0..<packed.height { for x in (sector*stride)..<((sector+1)*stride) {
                let value=packed.metres[y*packed.width+x]
                if value.isFinite { recovered.append(value) }
            } }
            XCTAssertEqual(recovered,s.metres[sector])
            XCTAssertGreaterThanOrEqual(packed.denominator,s.metres[sector].count)
        }
    }
    func testVersionedProfileReloadsAcrossNormalRestartWithoutWorldAnchors() throws {
        let p=confirmed(),data=try p.data(),reloaded=try MountProfile.load(data)
        XCTAssertEqual(reloaded,p);XCTAssertEqual(reloaded.id,p.id)
        XCTAssertTrue(reloaded.readyForReuse)
        let string=String(decoding:data,as:UTF8.self)
        XCTAssertFalse(string.contains("worldAnchor"));XCTAssertFalse(string.contains("token"))
        let newWorld=rotation([0,1,0],127)*neutral
        let newPose=try XCTUnwrap(CalibratedMountGeometry.cameraToLevel(newWorld))
        XCTAssertNoThrow(try CalibratedMountGeometry.validate(reloaded,camera:camera,pose:newPose,height:1))
    }
    func testUnconfirmedCorruptOldAndIncompatibleProfilesCannotReuse() throws {
        XCTAssertThrowsError(try MountProfile.load(profile().data()))
        var p=confirmed();p.version=999;XCTAssertThrowsError(try MountProfile.load(p.data()))
        p=confirmed();p.lowObstacleVerified=false;XCTAssertThrowsError(try MountProfile.load(p.data()))
        let different=MountCamera(device:"another",imageWidth:1920,imageHeight:1440,depthWidth:256,depthHeight:192,k:camera.k,display:camera.display)
        XCTAssertThrowsError(try CalibratedMountGeometry.validate(confirmed(),camera:different,pose:neutral,height:1))
        XCTAssertThrowsError(try MountProfile.load(Data("{}".utf8)))
    }
    func testNeutralWindowRejectsOldAndFutureCapturesEvenWhenOrdered() {
        var w=StableMountWindow()
        XCTAssertFalse(w.observe(timestamp:1,now:2,pose:neutral,height:1,usable:true))
        XCTAssertEqual(w.count,0)
        XCTAssertFalse(w.observe(timestamp:3,now:2,pose:neutral,height:1,usable:true))
        XCTAssertEqual(w.count,0)
    }
    func testStableWindowRejectsMovementReplaysGapsAndLoss() {
        var w=StableMountWindow(),ready=false
        for i in 0..<14 { ready=w.observe(timestamp:Double(i)*0.21,pose:neutral,height:1,usable:true) }
        XCTAssertTrue(ready)
        XCTAssertFalse(w.observe(timestamp:2.73,pose:neutral,height:1,usable:true));XCTAssertEqual(w.count,0)
        _=w.observe(timestamp:3,pose:neutral,height:1,usable:true)
        XCTAssertFalse(w.observe(timestamp:3.2,pose:rotation([1,0,0],4)*neutral,height:1,usable:true))
        XCTAssertEqual(w.count,0)
        _=w.observe(timestamp:4,pose:neutral,height:1,usable:true)
        XCTAssertFalse(w.observe(timestamp:5,pose:neutral,height:1,usable:true));XCTAssertEqual(w.count,0)
        _=w.observe(timestamp:6,pose:neutral,height:1,usable:true)
        XCTAssertFalse(w.observe(timestamp:6.2,pose:neutral,height:1,usable:false))
    }
}
