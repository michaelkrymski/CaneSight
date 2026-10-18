import SwiftUI

@main
struct CaneSightApp: App {
    @StateObject private var camera = CameraController()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView(camera: camera)
                .onChange(of: scenePhase) { phase in
                    camera.setActive(phase == .active)
                }
                .onAppear { camera.setActive(scenePhase == .active) }
        }
    }
}
