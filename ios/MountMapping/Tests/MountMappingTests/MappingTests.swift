import XCTest
import CaneSightDepth
import CaneSightMountMapping

final class MappingTests: XCTestCase {
    func raster() -> DepthFrame {
        DepthFrame(width: 6, height: 3, metres: (1...18).map(Float.init),
            confidence: (0..<18).map { UInt8($0 % 3) }, captureTimestampSeconds: 123,
            mode: .replay, tracking: .normal)
    }

    func testPortraitRotatesBothPlanesWithoutInterpolatingOrChangingProvenance() throws {
        let transform = try DisplayMapping(a: 0,b: -1,c: 1,d: 0,tx: 0,ty: 1)
        let result = try transform.prepare(raster())
        XCTAssertEqual(result.frame.width, 3); XCTAssertEqual(result.frame.height, 6)
        let expected: [Float] = [6,12,18,5,11,17,4,10,16,3,9,15,2,8,14,1,7,13]
        XCTAssertEqual(result.frame.metres, expected)
        XCTAssertEqual(result.frame.confidence, expected.map { UInt8((Int($0)-1)%3) })
        XCTAssertEqual(result.frame.captureTimestampSeconds, 123)
        XCTAssertEqual(result.frame.mode, .replay)
        XCTAssertEqual(Set(result.frame.metres).count, 18)
    }

    func testOppositeQuarterTurnAndHalfTurnHaveIndependentPixelOracles() throws {
        let clockwise = try DisplayMapping(a: 0,b: 1,c: -1,d: 0,tx: 1,ty: 0)
        XCTAssertEqual(try clockwise.prepare(raster()).frame.metres,
            [13,7,1,14,8,2,15,9,3,16,10,4,17,11,5,18,12,6])
        let half = try DisplayMapping(a: -1,b: 0,c: 0,d: -1,tx: 1,ty: 1)
        XCTAssertEqual(try half.prepare(raster()).frame.metres, (1...18).reversed().map(Float.init))
    }

    func testAspectFillCropUsesOnlyTheVisibleSensorRegion() throws {
        let transform = try DisplayMapping(a: 2,b: 0,c: 0,d: 1,tx: -0.5,ty: 0)
        let result = try transform.prepare(raster())
        XCTAssertEqual(result.frame.metres, raster().metres)
        XCTAssertEqual(result.region.xMin, 0.25, accuracy: 0.000001)
        XCTAssertEqual(result.region.xMax, 0.75, accuracy: 0.000001)
        XCTAssertEqual(result.region.yMin, 0); XCTAssertEqual(result.region.yMax, 1)
    }

    func testMirroredSingularShearedAndNonfiniteTransformsAreRejected() {
        for values: [Double] in [[-1,0,0,1,1,0],[0,0,0,0,0,0],
                                [1,0.1,0,1,0,0],[1,0,0,1,.nan,0],
                                [101,0,0,1,0,0]] {
            XCTAssertThrowsError(try DisplayMapping(a: values[0],b: values[1],c: values[2],d: values[3],tx: values[4],ty: values[5]))
        }
    }

    func testLetterboxOrOutOfFrameCropCannotInventSamples() throws {
        let transform = try DisplayMapping(a: 0.5,b: 0,c: 0,d: 1,tx: 0.25,ty: 0)
        XCTAssertThrowsError(try transform.prepare(raster()))
    }

    func testMalformedGeometryAndMissingConfidenceAreRejected() throws {
        let identity = try DisplayMapping(a: 1,b: 0,c: 0,d: 1,tx: 0,ty: 0)
        for frame in [DepthFrame(width: 6,height: 3,metres: [],confidence: [],captureTimestampSeconds: 0,mode: .live,tracking: .normal),
                      DepthFrame(width: 6,height: 3,metres: raster().metres,confidence: nil,captureTimestampSeconds: 0,mode: .live,tracking: .normal)] {
            XCTAssertThrowsError(try identity.prepare(frame))
        }
    }

    func summary(target: Int, time: Double, mode: DepthMode = .live,
                 tracking: DepthTracking = .normal) throws -> DepthSectorSummary {
        let values: [Float] = (0..<108).map { ($0%9)/3 == target ? 1 : 3 }
        return DepthSectorProcessor(configuration: try DepthSectorConfiguration()).process(
            DepthFrame(width: 9,height: 12,metres: values,confidence: [UInt8](repeating: 2,count: 108),
                captureTimestampSeconds: time,mode: mode,tracking: tracking))
    }
    func geometry(scale: Double = 1) throws -> MappingGeometry {
        MappingGeometry(width: 9,height: 12,mapping: try DisplayMapping(a: scale,b: 0,c: 0,d: 1,tx: 0,ty: 0))
    }

    func testThreeDistinctCapturesPerPhysicalTargetAreRequired() throws {
        var check = MountCheck(); let geo = try geometry(); check.observeGeometry(geo)
        XCTAssertFalse(check.complete)
        for index in 0..<9 {
            try check.record(summary: summary(target: index/3,time: Double(index)),geometry: geo,receipt: Double(index),now: Double(index))
            XCTAssertEqual(check.complete, index == 8)
        }
        XCTAssertEqual(check.counts, [3,3,3]); XCTAssertNil(check.nextTarget)
    }

    func testWrongSideAndReusedCaptureCannotEarnVerification() throws {
        var check = MountCheck(); let geo = try geometry(); check.observeGeometry(geo)
        XCTAssertThrowsError(try check.record(summary: summary(target: 2,time: 1),geometry: geo,receipt: 1,now: 1))
        XCTAssertEqual(check.counts, [0,0,0])
        try check.record(summary: summary(target: 0,time: 2),geometry: geo,receipt: 2,now: 2)
        XCTAssertThrowsError(try check.record(summary: summary(target: 0,time: 2),geometry: geo,receipt: 3,now: 3))
        XCTAssertEqual(check.counts, [1,0,0])
    }

    func testReplayOrUnknownTrackingCannotQualifyAsPhysicalEvidence() throws {
        var check = MountCheck(); let geo = try geometry(); check.observeGeometry(geo)
        XCTAssertThrowsError(try check.record(summary: summary(target: 0,time: 1,mode: .replay),geometry: geo,receipt: 1,now: 1))
        XCTAssertThrowsError(try check.record(summary: summary(target: 0,time: 2,tracking: .limited),geometry: geo,receipt: 2,now: 2))
        XCTAssertEqual(check.counts, [0,0,0])
    }

    func testTransformChangeAndResetInvalidatePreviousChecks() throws {
        var check = MountCheck(); let geo = try geometry(); check.observeGeometry(geo)
        try check.record(summary: summary(target: 0,time: 1),geometry: geo,receipt: 1,now: 1)
        check.observeGeometry(try geometry(scale: 2))
        XCTAssertEqual(check.counts, [0,0,0])
        XCTAssertThrowsError(try check.record(summary: summary(target: 0,time: 2),geometry: geo,receipt: 2,now: 2))
        XCTAssertNil(check.geometry)
    }

    func testDelayedOrClockReversedRecordClearsPreviousProgress() throws {
        for secondNow in [0.5, 2.5, Double.nan] {
            var check = MountCheck(); let geo = try geometry(); check.observeGeometry(geo)
            try check.record(summary: summary(target: 0,time: 1),geometry: geo,receipt: 1,now: 1)
            XCTAssertThrowsError(try check.record(summary: summary(target: 0,time: 2),geometry: geo,receipt: 2,now: secondNow))
            XCTAssertEqual(check.counts, [0,0,0])
        }
    }
}
