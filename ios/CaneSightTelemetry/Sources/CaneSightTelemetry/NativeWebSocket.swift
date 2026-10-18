import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public protocol TelemetrySocket: Sendable {
    func send(_ data: Data) async throws
    func receive() async throws -> Data
    func cancel()
}
/// Default TLS trust/hostname verification. No custom trust override, cookies,
/// credential store, response cache, URL token or redirect credential forwarding.
public final class NativeWebSocket: NSObject, TelemetrySocket, URLSessionWebSocketDelegate, @unchecked Sendable {
    private let lock = NSLock()
    private var session: URLSession?
    private var task: URLSessionWebSocketTask?
    private var opening: CheckedContinuation<Void, Error>?
    private var ended = false
    public static func request(for grant: PhoneSession) -> URLRequest {
        var request = URLRequest(url: grant.endpoint)
        request.setValue("Bearer " + grant.token, forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 5
        return request
    }
    public static func connect(_ grant: PhoneSession) async throws -> any TelemetrySocket {
        let socket = NativeWebSocket()
        do { try await withTaskCancellationHandler(operation: {
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                socket.begin(grant, continuation: continuation)
            }
        }, onCancel: { socket.cancel() }) }
        catch { socket.cancel(); throw error }
        return socket
    }
    private func begin(_ grant: PhoneSession, continuation: CheckedContinuation<Void, Error>) {
        lock.lock(); defer { lock.unlock() }
        guard !ended else { continuation.resume(throwing: TelemetryError.closed); return }
        opening = continuation
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil; configuration.httpCookieStorage = nil
        configuration.urlCredentialStorage = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.connectionProxyDictionary = [:]
        let queue = OperationQueue(); queue.maxConcurrentOperationCount = 1
        let session = URLSession(configuration: configuration, delegate: self, delegateQueue: queue)
        self.session = session
        let task = session.webSocketTask(with: Self.request(for: grant))
        task.maximumMessageSize = 8192; self.task = task; task.resume()
    }
    private func current() throws -> URLSessionWebSocketTask {
        lock.lock(); defer { lock.unlock() }
        guard !ended, let task else { throw TelemetryError.closed }
        return task
    }
    private func classify(_ task: URLSessionTask?, _ error: Error? = nil) -> TelemetryError {
        let status = (task?.response as? HTTPURLResponse)?.statusCode ?? 0
        let close = (task as? URLSessionWebSocketTask)?.closeCode.rawValue ?? 0
        let code = (error as NSError?)?.code ?? 0
        if (300..<400).contains(status) || [401,403,409].contains(status)
            || [1008,1009,4401,4403,4409].contains(close)
            || [-1200,-1201,-1202,-1203,-1204,-1205,-1206].contains(code) { return .rejected }
        return .connection
    }
    public func send(_ data: Data) async throws {
        guard data.count <= 8192 else { throw TelemetryError.invalidControl }
        let task = try current()
        do { try await task.send(.data(data)) }
        catch { throw classify(task, error) }
    }
    public func receive() async throws -> Data {
        let task = try current()
        do {
            let message = try await task.receive()
            let data: Data
            switch message {
            case .data(let value): data = value
            case .string(let value): data = Data(value.utf8)
            @unknown default: throw TelemetryError.invalidControl
            }
            guard data.count <= 8192 else { throw TelemetryError.invalidControl }
            return data
        } catch let error as TelemetryError { throw error }
        catch { throw classify(task, error) }
    }
    public func cancel() {
        lock.lock()
        ended = true
        let task = self.task, session = self.session, continuation = opening
        self.task = nil; self.session = nil; opening = nil
        lock.unlock()
        task?.cancel(with: .goingAway, reason: nil); session?.invalidateAndCancel()
        continuation?.resume(throwing: TelemetryError.closed)
    }
    public func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        lock.lock(); let continuation = opening; opening = nil; lock.unlock()
        continuation?.resume()
    }
    public func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        lock.lock(); let continuation = opening; opening = nil; lock.unlock()
        continuation?.resume(throwing: classify(task, error))
    }
    public func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                           didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        lock.lock(); let continuation = opening; opening = nil; lock.unlock()
        continuation?.resume(throwing: classify(webSocketTask))
    }
    public func urlSession(_ session: URLSession, task: URLSessionTask,
                           willPerformHTTPRedirection response: HTTPURLResponse,
                           newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}
