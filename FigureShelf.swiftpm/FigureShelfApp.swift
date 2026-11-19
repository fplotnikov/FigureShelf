import SwiftUI

@main
struct FigureShelfApp: App {
    init() {
        RealModelLibrary.shared.preloadAll()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.light)   // the toy palette is designed for light mode
        }
    }
}
