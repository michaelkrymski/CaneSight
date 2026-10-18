import Foundation

public enum DepthMode: String, Codable, Equatable, Sendable { case live, replay }
public enum DepthTracking: String, Codable, Equatable, Sendable { case normal, limited, unavailable }
public enum ConfidenceThreshold: UInt8, Sendable { case medium = 1, high = 2 }
public enum DepthInputError: Error { case invalidConfiguration, invalidDimensions, invalidStride, truncatedPlane, oversizedPlane }

/// All names refer to input depth-image columns, never verified physical sides.
public enum DepthImageSector: String, CaseIterable, Equatable, Sendable {
    case imageLeft, imageCenter, imageRight
}

public struct NormalizedDepthRegion: Sendable {
    public let xMin: Double
    public let yMin: Double
    public let xMax: Double
    public let yMax: Double
    public static let full = try! NormalizedDepthRegion(xMin: 0, yMin: 0, xMax: 1, yMax: 1)

    public init(xMin: Double, yMin: Double, xMax: Double, yMax: Double) throws {
        guard [xMin, yMin, xMax, yMax].allSatisfy({ $0.isFinite && $0 >= 0 && $0 <= 1 }),
              xMin < xMax, yMin < yMax else { throw DepthInputError.invalidConfiguration }
        self.xMin = xMin; self.yMin = yMin; self.xMax = xMax; self.yMax = yMax
    }
}

/// Initial engineering defaults, not validated sensor or stopping-distance limits.
public struct DepthSectorConfiguration: Sendable {
    public let minimumConfidence: ConfidenceThreshold
    public let minimumValidFraction: Double
    public let minimumValidSamples: Int
    public let nearPercentile: Double
    public let region: NormalizedDepthRegion

    public init(minimumConfidence: ConfidenceThreshold = .high,
                minimumValidFraction: Double = 0.25, minimumValidSamples: Int = 32,
                nearPercentile: Double = 0.10, region: NormalizedDepthRegion = .full) throws {
        guard minimumValidFraction.isFinite, minimumValidFraction > 0, minimumValidFraction <= 1,
              (1...DepthLimits.maximumPixels).contains(minimumValidSamples),
              nearPercentile.isFinite, nearPercentile > 0, nearPercentile <= 0.5 else {
            throw DepthInputError.invalidConfiguration
        }
        self.minimumConfidence = minimumConfidence
        self.minimumValidFraction = minimumValidFraction
        self.minimumValidSamples = minimumValidSamples
        self.nearPercentile = nearPercentile
        self.region = region
    }
}

public enum DepthLimits {
    public static let maximumPixels = 262_144
    public static let maximumDimension = 2048
    public static let maximumPlaneBytes = 16_777_216

    public static func pixelCount(width: Int, height: Int) throws -> Int {
        guard width >= 3, height >= 1, width <= maximumDimension, height <= maximumDimension,
              width <= maximumPixels / height else { throw DepthInputError.invalidDimensions }
        return width * height
    }

    public static func validTimestamp(_ value: Double) -> Bool {
        // Preserve seconds verbatim, while keeping a later milliseconds encoding bounded.
        value.isFinite && value >= 0 && value <= 9_007_199_254_740
    }
}

/// Owned packed samples. Input validation happens before any processor indexing.
/// Replay producers must supply .replay explicitly. There is no implicit mode.
public struct DepthFrame: Sendable {
    public let width: Int
    public let height: Int
    public let metres: [Float]
    public let confidence: [UInt8]?
    public let captureTimestampSeconds: Double
    public let mode: DepthMode
    public let tracking: DepthTracking

    public init(width: Int, height: Int, metres: [Float], confidence: [UInt8]?,
                captureTimestampSeconds: Double, mode: DepthMode, tracking: DepthTracking) {
        self.width = width; self.height = height; self.metres = metres; self.confidence = confidence
        self.captureTimestampSeconds = captureTimestampSeconds; self.mode = mode; self.tracking = tracking
    }
}

public enum SectorEvidence: String, Equatable, Sendable {
    case measured, insufficientCoverage, insufficientSamples, unavailable
}
public enum DepthFrameReason: String, Equatable, Sendable {
    case processedFrame, invalidTimestamp, trackingUnavailable, invalidDimensions
    case missingConfidence, malformedSamples, emptyRegion
    case unsupportedDevice, missingDepth, invalidPixelFormat, unavailableBuffer
}

public struct DepthSector: Equatable, Sendable {
    public let position: DepthImageSector
    public let distanceMetres: Double?
    public let validFraction: Double?
    public let validSamples: Int
    public let totalSamples: Int
    public let evidence: SectorEvidence
}

/// Internal sensor summary, not a shared v1 packet or a haptic command.
public struct DepthSectorSummary: Equatable, Sendable {
    public let mode: DepthMode
    public let captureTimestampSeconds: Double?
    public let reason: DepthFrameReason
    public let sectors: [DepthSector]
    public let coordinateSpace = "depth_image_columns"
    public let physicalMappingVerified = false

    public static func unavailable(mode: DepthMode, captureTimestampSeconds: Double?,
                                   reason: DepthFrameReason) -> Self {
        let timestamp = captureTimestampSeconds.flatMap { DepthLimits.validTimestamp($0) ? $0 : nil }
        return Self(mode: mode, captureTimestampSeconds: timestamp, reason: reason,
                    sectors: DepthImageSector.allCases.map {
                        DepthSector(position: $0, distanceMetres: nil, validFraction: nil,
                                    validSamples: 0, totalSamples: 0, evidence: .unavailable)
                    })
    }
}

/// Stateless: bad/missing evidence cannot reuse a previous distance or timestamp.
public struct DepthSectorProcessor: Sendable {
    public let configuration: DepthSectorConfiguration

    public init(configuration: DepthSectorConfiguration) { self.configuration = configuration }

    public func process(_ frame: DepthFrame) -> DepthSectorSummary {
        func unknown(_ reason: DepthFrameReason) -> DepthSectorSummary {
            .unavailable(mode: frame.mode, captureTimestampSeconds: frame.captureTimestampSeconds, reason: reason)
        }
        guard DepthLimits.validTimestamp(frame.captureTimestampSeconds) else { return unknown(.invalidTimestamp) }
        guard frame.tracking == .normal else { return unknown(.trackingUnavailable) }
        guard let count = try? DepthLimits.pixelCount(width: frame.width, height: frame.height) else {
            return unknown(.invalidDimensions)
        }
        guard let confidence = frame.confidence else { return unknown(.missingConfidence) }
        guard frame.metres.count == count, confidence.count == count else { return unknown(.malformedSamples) }
        let roi = configuration.region
        let x0 = Int(ceil(roi.xMin * Double(frame.width)))
        let x1 = Int(floor(roi.xMax * Double(frame.width)))
        let y0 = Int(ceil(roi.yMin * Double(frame.height)))
        let y1 = Int(floor(roi.yMax * Double(frame.height)))
        guard x1 - x0 >= 3, y1 > y0 else { return unknown(.emptyRegion) }

        var sectors: [DepthSector] = []
        for (index, position) in DepthImageSector.allCases.enumerated() {
            let start = x0 + (x1 - x0) * index / 3
            let end = x0 + (x1 - x0) * (index + 1) / 3
            let total = (end - start) * (y1 - y0)
            var valid: [Float] = []
            valid.reserveCapacity(total)
            for y in y0..<y1 {
                for x in start..<end {
                    let offset = y * frame.width + x
                    let value = frame.metres[offset]
                    let level = confidence[offset]
                    if value.isFinite && value > 0 && level >= configuration.minimumConfidence.rawValue && level <= 2 {
                        valid.append(value)
                    }
                }
            }
            let fraction = Double(valid.count) / Double(total)
            let evidence: SectorEvidence
            var distance: Double?
            if fraction < configuration.minimumValidFraction {
                evidence = .insufficientCoverage
            } else if valid.count < configuration.minimumValidSamples {
                evidence = .insufficientSamples
            } else {
                valid.sort()
                let rank = max(0, Int(ceil(configuration.nearPercentile * Double(valid.count))) - 1)
                distance = Double(valid[rank])
                evidence = .measured
            }
            sectors.append(DepthSector(position: position, distanceMetres: distance, validFraction: fraction,
                                       validSamples: valid.count, totalSamples: total, evidence: evidence))
        }
        return DepthSectorSummary(mode: frame.mode, captureTimestampSeconds: frame.captureTimestampSeconds,
                                  reason: .processedFrame, sectors: sectors)
    }
}
