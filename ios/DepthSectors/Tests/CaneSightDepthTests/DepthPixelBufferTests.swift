#if canImport(CoreVideo)
import CoreVideo
import Foundation
import XCTest
import CaneSightDepth
import CaneSightDepthARKit

/// Apple-only buffer tests. Authored here; execution requires the Apple SDK.
final class DepthPixelBufferTests: XCTestCase {
    enum SetupError: Error { case cannotLock }

    func buffer(width: Int = 6, height: Int = 2, format: OSType) throws -> CVPixelBuffer {
        var output: CVPixelBuffer?
        let attributes = [kCVPixelBufferBytesPerRowAlignmentKey as String: 64] as CFDictionary
        let result = CVPixelBufferCreate(kCFAllocatorDefault, width, height, format, attributes, &output)
        XCTAssertEqual(result, kCVReturnSuccess)
        return try XCTUnwrap(output)
    }

    func fill(_ buffer: CVPixelBuffer, value: Float) throws {
        guard CVPixelBufferLockBaseAddress(buffer, []) == kCVReturnSuccess else { throw SetupError.cannotLock }
        defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
        let base = try XCTUnwrap(CVPixelBufferGetBaseAddress(buffer))
        for y in 0..<CVPixelBufferGetHeight(buffer) {
            for x in 0..<CVPixelBufferGetWidth(buffer) {
                base.storeBytes(of: value, toByteOffset: y * CVPixelBufferGetBytesPerRow(buffer) + x * 4, as: Float.self)
            }
        }
    }

    func fillConfidence(_ buffer: CVPixelBuffer, value: UInt8 = 2) throws {
        guard CVPixelBufferLockBaseAddress(buffer, []) == kCVReturnSuccess else { throw SetupError.cannotLock }
        defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
        let base = try XCTUnwrap(CVPixelBufferGetBaseAddress(buffer))
        for y in 0..<CVPixelBufferGetHeight(buffer) {
            for x in 0..<CVPixelBufferGetWidth(buffer) {
                base.storeBytes(of: value, toByteOffset: y * CVPixelBufferGetBytesPerRow(buffer) + x, as: UInt8.self)
            }
        }
    }

    func testPaddedNativePlanesProduceOwnedSamplesBeforeUnlock() throws {
        let depth = try buffer(format: kCVPixelFormatType_DepthFloat32)
        let confidence = try buffer(format: kCVPixelFormatType_OneComponent8)
        try fill(depth, value: 2); try fillConfidence(confidence)
        let frame = try DepthPixelBufferReader.copyFrame(depth: depth, confidence: confidence,
            captureTimestampSeconds: 123.125, mode: .replay, tracking: .normal)
        try fill(depth, value: 9); try fillConfidence(confidence, value: 0)
        XCTAssertEqual(frame.metres, Array(repeating: 2, count: 12))
        XCTAssertEqual(frame.confidence, Array(repeating: 2, count: 12))
        XCTAssertEqual(frame.captureTimestampSeconds, 123.125)
        XCTAssertEqual(frame.mode, .replay)
    }

    func testMismatchedDimensionsAndUnsupportedFormatAreRejected() throws {
        let depth = try buffer(format: kCVPixelFormatType_DepthFloat32)
        let wrongSize = try buffer(width: 3, format: kCVPixelFormatType_OneComponent8)
        let wrongFormat = try buffer(format: kCVPixelFormatType_32BGRA)
        for confidence in [wrongSize, wrongFormat] {
            XCTAssertThrowsError(try DepthPixelBufferReader.copyFrame(depth: depth, confidence: confidence,
                captureTimestampSeconds: 1, mode: .replay, tracking: .normal))
        }
    }
}
#endif
