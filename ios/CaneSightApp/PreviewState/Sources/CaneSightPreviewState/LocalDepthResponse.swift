/// Visual bench indicator only. No policy, motor, movement or clear-path verdict.
public enum LocalDepthResponse: String, Sendable {
    case unknown = "Unknown"
    case near = "Near · simulated response"
    case aboveThreshold = "Above demo threshold"

    public static let thresholdMetres = 1.2
    public init(distanceMetres: Double?) {
        guard let value = distanceMetres, value.isFinite, value > 0 else {
            self = .unknown; return
        }
        self = value <= Self.thresholdMetres ? .near : .aboveThreshold
    }
}
