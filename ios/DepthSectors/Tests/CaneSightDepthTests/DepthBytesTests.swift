import Foundation
import XCTest
import CaneSightDepth

final class DepthBytesTests: XCTestCase {
    func put(_ value: Float, at offset: Int, into data: inout Data) {
        var bits = value.bitPattern.littleEndian
        withUnsafeBytes(of: &bits) { data.replaceSubrange(offset..<(offset + 4), with: $0) }
    }

    func testPaddedRowsAreDecodedIndependentlyForDepthAndConfidence() throws {
        var depth = Data(repeating: 255, count: 32)
        var confidence = Data(repeating: 255, count: 16)
        for y in 0..<2 {
            for x in 0..<3 {
                put(Float(y * 3 + x + 1), at: y * 16 + x * 4, into: &depth)
                confidence[y * 8 + x] = 2
            }
        }
        let frame = try DepthByteDecoder.decode(width: 3, height: 2, depth: depth, depthBytesPerRow: 16,
            confidence: confidence, confidenceBytesPerRow: 8, captureTimestampSeconds: 12.25,
            mode: .replay, tracking: .normal)
        XCTAssertEqual(frame.metres, [1, 2, 3, 4, 5, 6])
        XCTAssertEqual(frame.confidence, [2, 2, 2, 2, 2, 2])
        XCTAssertEqual(frame.captureTimestampSeconds, 12.25)
        XCTAssertEqual(frame.mode, .replay)
        XCTAssertThrowsError(try DepthByteDecoder.decode(width: 3, height: 2,
            depth: Data(depth.prefix(27)), depthBytesPerRow: 16, confidence: confidence,
            confidenceBytesPerRow: 8, captureTimestampSeconds: 12.25, mode: .replay, tracking: .normal))
    }

    func testInvalidOrOverflowingGeometryAndStrideThrowBeforeReading() {
        for (width, height) in [(Int.max, 1), (3, Int.max), (3, 0), (2, 2), (2048, 2048)] {
            XCTAssertThrowsError(try DepthLimits.pixelCount(width: width, height: height))
        }
        for stride in [-1, 0, 11, Int.max] {
            XCTAssertThrowsError(try DepthByteDecoder.span(width: 3, height: 2, bytesPerPixel: 4, bytesPerRow: stride))
        }
        XCTAssertThrowsError(try DepthByteDecoder.span(width: 3, height: 2, bytesPerPixel: 8, bytesPerRow: 24))
        XCTAssertThrowsError(try DepthByteDecoder.decode(width: 3, height: 2,
            depth: Data(repeating: 0, count: 24), depthBytesPerRow: 12,
            confidence: Data(repeating: 2, count: 5), confidenceBytesPerRow: 3,
            captureTimestampSeconds: 1, mode: .replay, tracking: .normal))
    }

    func testNonfiniteFloatBitsArePreservedForProcessorToReject() throws {
        var depth = Data(repeating: 0, count: 12)
        put(.nan, at: 0, into: &depth); put(.infinity, at: 4, into: &depth); put(-1, at: 8, into: &depth)
        let frame = try DepthByteDecoder.decode(width: 3, height: 1, depth: depth, depthBytesPerRow: 12,
            confidence: Data([2, 2, 2]), confidenceBytesPerRow: 3,
            captureTimestampSeconds: 1, mode: .replay, tracking: .normal)
        XCTAssertTrue(frame.metres[0].isNaN)
        XCTAssertEqual(frame.metres[1], .infinity)
        let processor = DepthSectorProcessor(configuration: try DepthSectorConfiguration(minimumValidSamples: 1))
        XCTAssertTrue(processor.process(frame).sectors.allSatisfy { $0.distanceMetres == nil && $0.validFraction == 0 })
    }
}
