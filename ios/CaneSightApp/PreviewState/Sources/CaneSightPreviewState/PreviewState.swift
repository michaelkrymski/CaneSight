import Foundation

/// Local preview delivery only. Callback recency is NOT sensor capture age,
/// clock calibration, protocol eligibility or permission for motor output.
public struct PreviewState<Value> {
    public private(set) var epoch = UUID()
    public private(set) var value: Value?
    private var lastReceipt: Double?
    private var lastSource: Double?
    private var lastNow: Double?
    private var clockFailed = false

    public init() {}

    public mutating func invalidate() {
        epoch = UUID()
        value = nil
        lastReceipt = nil
        lastSource = nil
        lastNow = nil
        clockFailed = false
    }

    private mutating func validClock(_ now: Double) -> Bool {
        guard !clockFailed, now.isFinite, now >= 0,
              lastNow.map({ now >= $0 }) ?? true else {
            clockFailed = true
            value = nil
            return false
        }
        lastNow = now
        return true
    }

    @discardableResult
    public mutating func accept(_ input: Value, epoch: UUID, sourceSeconds: Double?,
                                receiptSeconds: Double, nowSeconds: Double) -> Bool {
        guard epoch == self.epoch else { return false }
        guard validClock(nowSeconds), let sourceSeconds,
              sourceSeconds.isFinite, sourceSeconds >= 0,
              receiptSeconds.isFinite, receiptSeconds >= 0,
              nowSeconds >= receiptSeconds, nowSeconds - receiptSeconds < 0.5,
              lastSource.map({ sourceSeconds > $0 }) ?? true,
              lastReceipt.map({ receiptSeconds >= $0 }) ?? true else {
            value = nil
            return false
        }
        value = input
        lastSource = sourceSeconds
        lastReceipt = receiptSeconds
        return true
    }

    /// Heartbeats cannot call accept or renew the callback receipt deadline.
    public mutating func tick(nowSeconds: Double) {
        guard validClock(nowSeconds) else { return }
        if let lastReceipt, nowSeconds - lastReceipt >= 0.5 { value = nil }
    }
}
