import SwiftUI

@main struct CaneSightApp: App {
    @StateObject private var services=AppServices()
    @Environment(\.scenePhase) private var scenePhase
    var body: some Scene {
        WindowGroup {
            ContentView(services: services)
                .onChange(of: scenePhase) { services.setActive($0 == .active) }
                .onAppear { services.setActive(scenePhase == .active) }
        }
    }
}
