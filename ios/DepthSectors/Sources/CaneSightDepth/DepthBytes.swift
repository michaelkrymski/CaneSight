import Foundation

/// Bounds and row-stride handling for owned Float32/UInt8 planes. This decoder
/// does not interpolate, rescale, fill holes, or infer a missing confidence map.
public enum DepthByteDecoder {
    public static func span(width: Int, height: Int, bytesPerPixel: Int, bytesPerRow: Int) throws -> Int {
        _ = try DepthLimits.pixelCount(width: width, height: height)
        guard bytesPerPixel == 1 || bytesPerPixel == 4,
              bytesPerRow >= width * bytesPerPixel,
              bytesPerRow <= DepthLimits.maximumPlaneBytes,
              bytesPerRow <= DepthLimits.maximumPlaneBytes / height else { throw DepthInputError.invalidStride }
        return (height - 1) * bytesPerRow + width * bytesPerPixel
    }

    /// The byte representation is explicitly little-endian IEEE Float32;
    /// current supported Apple iPhone/Mac targets use this representation.
    public static func decode(width: Int, height: Int, depth: Data, depthBytesPerRow: Int,
                              confidence: Data, confidenceBytesPerRow: Int,
                              captureTimestampSeconds: Double, mode: DepthMode,
                              tracking: DepthTracking) throws -> DepthFrame {
        let count = try DepthLimits.pixelCount(width: width, height: height)
        let depthSpan = try span(width: width, height: height, bytesPerPixel: 4, bytesPerRow: depthBytesPerRow)
        let confidenceSpan = try span(width: width, height: height, bytesPerPixel: 1, bytesPerRow: confidenceBytesPerRow)
        guard depth.count <= DepthLimits.maximumPlaneBytes, confidence.count <= DepthLimits.maximumPlaneBytes else {
            throw DepthInputError.oversizedPlane
        }
        guard depth.count >= depthSpan, confidence.count >= confidenceSpan else { throw DepthInputError.truncatedPlane }
        var values = [Float](repeating: 0, count: count)
        var levels = [UInt8](repeating: 0, count: count)
        depth.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            confidence.withUnsafeBytes { (confidenceRaw: UnsafeRawBufferPointer) in
                for y in 0..<height {
                    for x in 0..<width {
                        let bits = raw.loadUnaligned(fromByteOffset: y * depthBytesPerRow + x * 4, as: UInt32.self)
                        values[y * width + x] = Float(bitPattern: UInt32(littleEndian: bits))
                        levels[y * width + x] = confidenceRaw.load(fromByteOffset: y * confidenceBytesPerRow + x, as: UInt8.self)
                    }
                }
            }
        }
        return DepthFrame(width: width, height: height, metres: values, confidence: levels,
                          captureTimestampSeconds: captureTimestampSeconds, mode: mode, tracking: tracking)
    }
}
