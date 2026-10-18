import CaneSightDepth

#if canImport(CoreVideo)
import CoreVideo
import Foundation

public enum DepthPixelBufferReader {
    /// Copies while locked; no CVPixelBuffer/raw pointer escapes this function.
    public static func copyFrame(depth: CVPixelBuffer, confidence: CVPixelBuffer,
                                 captureTimestampSeconds: Double, mode: DepthMode,
                                 tracking: DepthTracking) throws -> DepthFrame {
        guard !CVPixelBufferIsPlanar(depth), !CVPixelBufferIsPlanar(confidence),
              CVPixelBufferGetPixelFormatType(depth) == kCVPixelFormatType_DepthFloat32,
              CVPixelBufferGetPixelFormatType(confidence) == kCVPixelFormatType_OneComponent8 else {
            throw DepthInputError.invalidConfiguration
        }
        let width = CVPixelBufferGetWidth(depth), height = CVPixelBufferGetHeight(depth)
        _ = try DepthLimits.pixelCount(width: width, height: height)
        guard CVPixelBufferGetWidth(confidence) == width, CVPixelBufferGetHeight(confidence) == height else {
            throw DepthInputError.invalidDimensions
        }
        let depthRow = CVPixelBufferGetBytesPerRow(depth), confidenceRow = CVPixelBufferGetBytesPerRow(confidence)
        let depthSpan = try DepthByteDecoder.span(width: width, height: height, bytesPerPixel: 4, bytesPerRow: depthRow)
        let confidenceSpan = try DepthByteDecoder.span(width: width, height: height, bytesPerPixel: 1, bytesPerRow: confidenceRow)
        guard CVPixelBufferGetDataSize(depth) >= depthSpan, CVPixelBufferGetDataSize(confidence) >= confidenceSpan else {
            throw DepthInputError.truncatedPlane
        }
        guard CVPixelBufferLockBaseAddress(depth, .readOnly) == kCVReturnSuccess else { throw DepthInputError.truncatedPlane }
        defer { CVPixelBufferUnlockBaseAddress(depth, .readOnly) }
        guard CVPixelBufferLockBaseAddress(confidence, .readOnly) == kCVReturnSuccess else { throw DepthInputError.truncatedPlane }
        defer { CVPixelBufferUnlockBaseAddress(confidence, .readOnly) }
        guard let depthBase = CVPixelBufferGetBaseAddress(depth), let confidenceBase = CVPixelBufferGetBaseAddress(confidence) else {
            throw DepthInputError.truncatedPlane
        }
        return try DepthByteDecoder.decode(width: width, height: height,
            depth: Data(bytes: depthBase, count: depthSpan), depthBytesPerRow: depthRow,
            confidence: Data(bytes: confidenceBase, count: confidenceSpan), confidenceBytesPerRow: confidenceRow,
            captureTimestampSeconds: captureTimestampSeconds, mode: mode, tracking: tracking)
    }
}
#endif

#if os(iOS) && canImport(ARKit)
import ARKit

@available(iOS 14.0, *)
public struct ARKitDepthAdapter {
    public let processor: DepthSectorProcessor

    public init(configuration: DepthSectorConfiguration) {
        processor = DepthSectorProcessor(configuration: configuration)
    }

    public static var supportsSceneDepth: Bool {
        ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
    }

    /// Caller owns session setup/lifecycle and dispatches work off the UI thread.
    /// Uses raw sceneDepth, not smoothed history. Never starts or reconfigures ARSession.
    public func process(_ frame: ARFrame) -> DepthSectorSummary {
        func unknown(_ reason: DepthFrameReason) -> DepthSectorSummary {
            .unavailable(mode: .live, captureTimestampSeconds: frame.timestamp, reason: reason)
        }
        guard Self.supportsSceneDepth else { return unknown(.unsupportedDevice) }
        guard DepthLimits.validTimestamp(frame.timestamp) else { return unknown(.invalidTimestamp) }
        guard case .normal = frame.camera.trackingState else { return unknown(.trackingUnavailable) }
        guard let depth = frame.sceneDepth else { return unknown(.missingDepth) }
        guard let confidence = depth.confidenceMap else { return unknown(.missingConfidence) }
        guard CVPixelBufferGetPixelFormatType(depth.depthMap) == kCVPixelFormatType_DepthFloat32,
              CVPixelBufferGetPixelFormatType(confidence) == kCVPixelFormatType_OneComponent8 else {
            return unknown(.invalidPixelFormat)
        }
        do {
            let owned = try DepthPixelBufferReader.copyFrame(depth: depth.depthMap, confidence: confidence,
                captureTimestampSeconds: frame.timestamp, mode: .live, tracking: .normal)
            return processor.process(owned)
        } catch {
            return unknown(.unavailableBuffer)
        }
    }
}
#endif
