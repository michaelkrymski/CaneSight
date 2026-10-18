import CaneSightDepth
import CaneSightTelemetry

/// A session-bound depth producer and bounded transport. The app owns enrollment,
/// verified source-clock selection, readiness and lifecycle calls. Nothing starts
/// in init and no sensor/network state is inferred from a conversion or dial.
public final class DepthTelemetryStream: Sendable {
    private let adapter: DepthTelemetryAdapter
    private let client: TelemetryClient

    public init(session: PhoneSession, clock: @escaping @Sendable () throws -> Double,
                socketFactory: @escaping TelemetryClient.SocketFactory = {
                    try await NativeWebSocket.connect($0)
                }) {
        adapter = DepthTelemetryAdapter(sessionMode: session.mode)
        client = TelemetryClient(session: session, clock: clock, socketFactory: socketFactory)
    }
    public func start() async { await client.start() }
    public func setProducerState(_ state: ProducerState) async { await client.setProducerState(state) }
    public func suspend() async { await client.suspend() }
    public func resume() async { await client.resume() }
    public func close() async { await client.close() }
    public func status() async -> TelemetryStatus { await client.status() }
    /// Synchronous latest-only handoff; no per-frame task, retained ARFrame or image.
    public func submit(_ summary: DepthSectorSummary) throws { try adapter.submit(summary, to: client) }
}
