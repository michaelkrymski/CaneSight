import Foundation
import CaneSightDepth

public enum MappingError: Error { case invalidTransform, mirrored, invalidFrame, invisibleRegion, unavailableTarget, wrongTarget, repeatedCapture, expired, geometryChanged }

/// ARKit normalized image -> normalized portrait viewport, top-left origins.
public struct DisplayMapping: Equatable, Sendable {
    public let a, b, c, d, tx, ty: Double
    private let swapped: Bool
    public init(a: Double, b: Double, c: Double, d: Double, tx: Double, ty: Double) throws {
        let values = [a,b,c,d,tx,ty]
        guard values.allSatisfy({ $0.isFinite && abs($0) <= 100 }) else { throw MappingError.invalidTransform }
        let epsilon = 0.000001
        let direct = abs(b) < epsilon && abs(c) < epsilon && abs(a) >= 0.01 && abs(d) >= 0.01
        let quarter = abs(a) < epsilon && abs(d) < epsilon && abs(b) >= 0.01 && abs(c) >= 0.01
        guard direct || quarter else { throw MappingError.invalidTransform }
        guard a*d-b*c > epsilon else { throw MappingError.mirrored }
        self.a=a; self.b=b; self.c=c; self.d=d; self.tx=tx; self.ty=ty; swapped=quarter
    }

    public func point(x: Double, y: Double) -> (x: Double, y: Double) {
        (a*x+c*y+tx, b*x+d*y+ty)
    }

    /// Exact pixel permutation: no interpolated depth/confidence or duplicated samples.
    /// Aspect-fill crop is expressed as an ROI for the original CS-014 processor.
    public func prepare(_ frame: DepthFrame) throws -> (frame: DepthFrame, region: NormalizedDepthRegion) {
        let count = try DepthLimits.pixelCount(width: frame.width, height: frame.height)
        guard frame.metres.count == count, let confidence = frame.confidence, confidence.count == count else {
            throw MappingError.invalidFrame
        }
        let width = swapped ? frame.height : frame.width
        let height = swapped ? frame.width : frame.height
        _ = try DepthLimits.pixelCount(width: width, height: height)
        var metres = [Float](repeating: 0, count: count)
        var levels = [UInt8](repeating: 0, count: count)
        for y in 0..<frame.height {
            for x in 0..<frame.width {
                let outX = swapped ? (c > 0 ? y : frame.height-1-y) : (a > 0 ? x : frame.width-1-x)
                let outY = swapped ? (b > 0 ? x : frame.width-1-x) : (d > 0 ? y : frame.height-1-y)
                let original = y*frame.width+x, output = outY*width+outX
                metres[output] = frame.metres[original]
                levels[output] = confidence[original]
            }
        }
        let corners = [(0.0,0.0),(0,1),(1,0),(1,1)].map { point(x: $0.0, y: $0.1) }
        let minX = corners.map(\.x).min()!, maxX = corners.map(\.x).max()!
        let minY = corners.map(\.y).min()!, maxY = corners.map(\.y).max()!
        // Unsupported letterboxing cannot fabricate missing input. The ARKit
        // aspect-fill viewport must be entirely covered by the sensor image.
        let tolerance = 0.000001
        guard minX <= tolerance, minY <= tolerance, maxX >= 1-tolerance, maxY >= 1-tolerance else {
            throw MappingError.invisibleRegion
        }
        let region = try NormalizedDepthRegion(xMin: max(0,-minX/(maxX-minX)),
            yMin: max(0,-minY/(maxY-minY)), xMax: min(1,(1-minX)/(maxX-minX)),
            yMax: min(1,(1-minY)/(maxY-minY)))
        return (DepthFrame(width: width, height: height, metres: metres, confidence: levels,
            captureTimestampSeconds: frame.captureTimestampSeconds, mode: frame.mode, tracking: frame.tracking), region)
    }

    public func process(_ frame: DepthFrame) throws -> DepthSectorSummary {
        let oriented = try prepare(frame)
        let config = try DepthSectorConfiguration(region: oriented.region)
        return DepthSectorProcessor(configuration: config).process(oriented.frame)
    }
}

public struct MappingGeometry: Equatable, Sendable {
    public let width, height: Int
    public let mapping: DisplayMapping
    public init(width: Int, height: Int, mapping: DisplayMapping) {
        self.width=width; self.height=height; self.mapping=mapping
    }
}

/// Explicit operator placement plus distinct fresh observations, bound to one
/// portrait/rear-forward bench session and exact transform. Never a motor grant.
public struct MountCheck: Sendable {
    public private(set) var counts = [0,0,0]
    public private(set) var geometry: MappingGeometry?
    private var lastSource: Double?
    private var lastNow: Double?
    public var complete: Bool { counts.allSatisfy { $0 >= 3 } }
    public var nextTarget: Int? { counts.firstIndex(where: { $0 < 3 }) }
    public init() {}
    public mutating func reset() { self = MountCheck() }

    public mutating func observeGeometry(_ value: MappingGeometry) {
        if let geometry, geometry != value { reset() }
        geometry = value
    }

    /// Caller must truthfully place a distinct broad target on the requested
    /// physical side. The software checks observed dominance, not human identity.
    public mutating func record(summary: DepthSectorSummary, geometry: MappingGeometry,
                                receipt: Double, now: Double) throws {
        guard self.geometry == geometry else { reset(); throw MappingError.geometryChanged }
        guard now.isFinite, receipt.isFinite, receipt >= 0, now >= receipt,
              now-receipt < 0.5, lastNow.map({ now >= $0 }) ?? true else {
            reset(); throw MappingError.expired
        }
        lastNow = now
        guard let source = summary.captureTimestampSeconds,
              source.isFinite, source >= 0, lastSource.map({ source > $0 }) ?? true else {
            throw MappingError.repeatedCapture
        }
        guard summary.mode == .live, summary.reason == .processedFrame,
              summary.sectors.count == 3,
              summary.sectors.map(\.position) == DepthImageSector.allCases else { throw MappingError.unavailableTarget }
        let distances = summary.sectors.compactMap(\.distanceMetres)
        guard distances.count == 3, distances.allSatisfy({ $0.isFinite && $0 > 0 }) else { throw MappingError.unavailableTarget }
        guard let target = nextTarget else { return }
        // Initial bench separation margin, not a calibrated ranging threshold.
        guard (0..<3).filter({ $0 != target }).allSatisfy({ distances[target]+0.2 <= distances[$0] }) else {
            throw MappingError.wrongTarget
        }
        lastSource = source
        counts[target] += 1
    }
}
