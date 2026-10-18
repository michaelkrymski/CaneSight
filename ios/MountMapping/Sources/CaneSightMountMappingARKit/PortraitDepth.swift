#if os(iOS) && canImport(ARKit)
import ARKit
import UIKit
import CoreVideo
import CaneSightDepth
import CaneSightDepthARKit
import CaneSightMountMapping

public struct PortraitObservation: Sendable {
    public let summary: DepthSectorSummary
    public let geometry: MappingGeometry
}

public enum PortraitDepth {
    public static let viewport = CGSize(width: 9, height: 16)
    /// Caller verifies actual interface AND physical device orientation are
    /// portrait; it owns ARSession lifecycle and bounded worker dispatch.
    public static func process(_ frame: ARFrame) throws -> PortraitObservation {
        guard ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth),
              case .normal = frame.camera.trackingState,
              let depth = frame.sceneDepth, let confidence = depth.confidenceMap else {
            throw MappingError.invalidFrame
        }
        let input = try DepthPixelBufferReader.copyFrame(depth: depth.depthMap, confidence: confidence,
            captureTimestampSeconds: frame.timestamp, mode: .live, tracking: .normal)
        let image = frame.camera.imageResolution
        guard image.width > 0, image.height > 0,
              abs(Double(input.width)/Double(input.height) - image.width/image.height) < 0.01 else {
            throw MappingError.invalidFrame
        }
        // Use this frame's actual camera/display rotation and aspect-fill crop,
        // rather than assigning raw depth-buffer columns to physical sides.
        let t = frame.displayTransform(for: .portrait, viewportSize: viewport)
        let mapping = try DisplayMapping(a: t.a, b: t.b, c: t.c, d: t.d, tx: t.tx, ty: t.ty)
        return PortraitObservation(summary: try mapping.process(input),
            geometry: MappingGeometry(width: input.width, height: input.height, mapping: mapping))
    }
}
#endif
