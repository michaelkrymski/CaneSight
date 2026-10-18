import Foundation
import XCTest
@testable import CaneSightDepth

final class DepthSectorsTests: XCTestCase {
    func processor(coverage: Double = 0.5, samples: Int = 2, percentile: Double = 0.1,
                   confidence: ConfidenceThreshold = .high,
                   region: NormalizedDepthRegion = .full) throws -> DepthSectorProcessor {
        DepthSectorProcessor(configuration: try DepthSectorConfiguration(minimumConfidence: confidence,
            minimumValidFraction: coverage, minimumValidSamples: samples, nearPercentile: percentile, region: region))
    }

    func frame(_ values: [Float] = [1, 1, 2, 2, 3, 3, 1, 1, 2, 2, 3, 3],
               confidence: [UInt8]? = Array(repeating: 2, count: 12), width: Int = 6, height: Int = 2,
               timestamp: Double = 42.125, tracking: DepthTracking = .normal) -> DepthFrame {
        DepthFrame(width: width, height: height, metres: values, confidence: confidence,
                   captureTimestampSeconds: timestamp, mode: .replay, tracking: tracking)
    }

    func assertUnknown(_ summary: DepthSectorSummary, reason: DepthFrameReason,
                       file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertEqual(summary.reason, reason, file: file, line: line)
        XCTAssertTrue(summary.sectors.allSatisfy { $0.distanceMetres == nil }, file: file, line: line)
        XCTAssertTrue(summary.sectors.allSatisfy { $0.validFraction == nil }, file: file, line: line)
    }

    func testColumnsTimestampModeAndUnverifiedPhysicalMapping() throws {
        let result = try processor().process(frame())
        XCTAssertEqual(result.reason, .processedFrame)
        XCTAssertEqual(result.sectors.map(\.position), [.imageLeft, .imageCenter, .imageRight])
        XCTAssertEqual(result.sectors.map(\.distanceMetres), [1, 2, 3])
        XCTAssertEqual(result.sectors.map(\.validFraction), [1, 1, 1])
        XCTAssertEqual(result.captureTimestampSeconds, 42.125)
        XCTAssertEqual(result.mode, .replay)
        XCTAssertEqual(result.coordinateSpace, "depth_image_columns")
        XCTAssertFalse(result.physicalMappingVerified)
    }

    func testNonfiniteZeroAndNegativeSamplesStayOutOfPercentileAndCoverage() throws {
        let values: [Float] = [.nan, 0, 1, -1, .infinity, 2, 0, 0, 0,
                               1, 1, 1, 2, 2, 2, 0, -.infinity, 0]
        let input = frame(values, confidence: Array(repeating: 2, count: 18), width: 9)
        let result = try processor().process(input)
        XCTAssertEqual(result.sectors.map(\.distanceMetres), [1, 2, nil])
        XCTAssertEqual(result.sectors.map(\.validSamples), [4, 4, 0])
        XCTAssertEqual(result.sectors[0].validFraction!, 4.0 / 6, accuracy: 0.000001)
        XCTAssertEqual(result.sectors[2].validFraction, 0)
        XCTAssertEqual(result.sectors[2].evidence, .insufficientCoverage)
    }

    func testLowAndUnrecognizedConfidenceNeverCountAsHighConfidence() throws {
        let input = frame(confidence: [2, 1, 2, 2, 255, 255, 0, 2, 2, 2, 2, 2])
        let high = try processor().process(input)
        XCTAssertEqual(high.sectors.map(\.validSamples), [2, 4, 2])
        XCTAssertEqual(high.sectors.map(\.validFraction), [0.5, 1, 0.5])
        let medium = try processor(confidence: .medium).process(input)
        XCTAssertEqual(medium.sectors.map(\.validSamples), [3, 4, 2])
        assertUnknown(try processor().process(frame(confidence: nil)), reason: .missingConfidence)
    }

    func testCoverageAndMinimumSampleGatesAreIndependentAndSectorLocal() throws {
        let input = frame(confidence: [2, 0, 2, 0, 2, 2, 0, 0, 2, 0, 2, 2])
        let result = try processor(samples: 3).process(input)
        XCTAssertEqual(result.sectors.map(\.distanceMetres), [nil, nil, 3])
        XCTAssertEqual(result.sectors.map(\.evidence), [.insufficientCoverage, .insufficientSamples, .measured])
        XCTAssertEqual(result.sectors.map(\.validFraction), [0.25, 0.5, 1])
    }

    func testNearestRankPercentileIsNotMinimumOrAverage() throws {
        var values = [Float](repeating: 2, count: 600)
        values[0] = 0.01
        values[1] = 20
        let result = try processor().process(frame(values, confidence: Array(repeating: 2, count: 600), height: 100))
        XCTAssertEqual(result.sectors[0].validSamples, 200)
        XCTAssertEqual(result.sectors[0].distanceMetres, 2)
        let median = try processor(percentile: 0.5).process(frame())
        XCTAssertEqual(median.sectors.map(\.distanceMetres), [1, 2, 3])
    }

    func testUnevenColumnsAndCroppedRowsHaveExactDenominators() throws {
        let region = try NormalizedDepthRegion(xMin: 0, yMin: 0.5, xMax: 1, yMax: 1)
        let input = frame([99, 99, 99, 99, 99, 99, 99, 1, 1, 2, 2, 3, 3, 3],
                          confidence: Array(repeating: 2, count: 14), width: 7)
        let result = try processor(samples: 1, region: region).process(input)
        XCTAssertEqual(result.sectors.map(\.totalSamples), [2, 2, 3])
        XCTAssertEqual(result.sectors.map(\.distanceMetres), [1, 2, 3])
        let narrow = try NormalizedDepthRegion(xMin: 0.1, yMin: 0, xMax: 0.2, yMax: 1)
        assertUnknown(try processor(region: narrow).process(frame()), reason: .emptyRegion)
    }

    func testMalformedDimensionsAndArraysFailClosedWithoutIndexing() throws {
        let sut = try processor()
        for input in [frame(width: Int.max), frame(height: 0), frame(width: -1),
                      frame(width: 2048, height: 2048), frame(width: 2)] {
            assertUnknown(sut.process(input), reason: .invalidDimensions)
        }
        assertUnknown(sut.process(frame([1])), reason: .malformedSamples)
        assertUnknown(sut.process(frame(confidence: [2])), reason: .malformedSamples)
    }

    func testBadTimestampTrackingOrMissingFrameCannotCarryPriorDistance() throws {
        let sut = try processor()
        XCTAssertEqual(sut.process(frame()).sectors[0].distanceMetres, 1)
        for timestamp in [Double.nan, .infinity, -1, Double.greatestFiniteMagnitude] {
            let result = sut.process(frame(timestamp: timestamp))
            assertUnknown(result, reason: .invalidTimestamp)
            XCTAssertNil(result.captureTimestampSeconds)
        }
        for tracking in [DepthTracking.limited, .unavailable] {
            let result = sut.process(frame(timestamp: 43, tracking: tracking))
            assertUnknown(result, reason: .trackingUnavailable)
            XCTAssertEqual(result.captureTimestampSeconds, 43)
        }
        assertUnknown(sut.process(frame(confidence: nil)), reason: .missingConfidence)
        XCTAssertEqual(sut.process(frame(timestamp: 44)).captureTimestampSeconds, 44)
    }

    func testInvalidConfigurationCannotCreatePermissiveGates() {
        for value in [Double.nan, .infinity, 0, -1, 1.1] {
            XCTAssertThrowsError(try DepthSectorConfiguration(minimumValidFraction: value))
        }
        for value in [Double.nan, .infinity, 0, -1, 0.51] {
            XCTAssertThrowsError(try DepthSectorConfiguration(nearPercentile: value))
        }
        for count in [0, -1, Int.max] {
            XCTAssertThrowsError(try DepthSectorConfiguration(minimumValidSamples: count))
        }
        XCTAssertThrowsError(try NormalizedDepthRegion(xMin: .nan, yMin: 0, xMax: 1, yMax: 1))
        XCTAssertThrowsError(try NormalizedDepthRegion(xMin: 1, yMin: 0, xMax: 0, yMax: 1))
    }

    func testAuthoredReplayFixtures() throws {
        struct Pack: Decodable {
            let version: Int
            let mode: String
            let cases: [Case]
            struct Case: Decodable {
                let id: String
                let width: Int
                let height: Int
                let metres: [Float]
                let confidence: [UInt8]?
                let timestamp: Double
                let tracking: DepthTracking
                let expectedDistances: [Double?]
                let expectedFractions: [Double?]
                let expectedTimestamp: Double?
                let expectedReason: String
            }
        }
        let url = try XCTUnwrap(Bundle.module.url(forResource: "replay", withExtension: "json", subdirectory: "Fixtures"))
        let decoder = JSONDecoder()
        decoder.nonConformingFloatDecodingStrategy = .convertFromString(positiveInfinity: "+inf", negativeInfinity: "-inf", nan: "nan")
        let pack = try decoder.decode(Pack.self, from: Data(contentsOf: url))
        XCTAssertEqual(pack.version, 1)
        XCTAssertEqual(pack.mode, "replay")
        let sut = try processor()
        for item in pack.cases {
            let input = frame(item.metres, confidence: item.confidence, width: item.width, height: item.height,
                              timestamp: item.timestamp, tracking: item.tracking)
            let actual = sut.process(input)
            XCTAssertEqual(actual.reason.rawValue, item.expectedReason, item.id)
            XCTAssertEqual(actual.sectors.map(\.distanceMetres), item.expectedDistances, item.id)
            XCTAssertEqual(actual.sectors.map(\.validFraction), item.expectedFractions, item.id)
            XCTAssertEqual(actual.captureTimestampSeconds, item.expectedTimestamp, item.id)
            XCTAssertEqual(actual.mode, .replay)
        }
    }
}
