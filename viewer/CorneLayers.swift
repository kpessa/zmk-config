// Corne Layers: a small window that shows the layer page live, at full size or as a
// mini player (the button in the title bar, or Window › Mini Player).
//
// Listens to the Corne's raw HID reports (needs Input Monitoring permission) and
// passes every key and consumer-key change to the page, which lights the key and
// follows the layer signals the keymap's macros tap. It only listens: nothing is
// intercepted, so typing, shortcuts and Plover are unaffected.
//
// It also switches Plover with the Steno layer: output on when the keyboard enters
// Steno, off when it leaves, starting Plover if it isn't running.
//
//   --log            print every HID value to stdout
//   --no-plover      leave Plover alone
//   --device NAME    listen to keyboards whose product name contains NAME
//                    (default "Corne"; "" for every keyboard)

import Cocoa
import IOKit.hid
import WebKit

let arguments = CommandLine.arguments
let logging = arguments.contains("--log")
let managePlover = !arguments.contains("--no-plover")
let stenoLayer = "Steno"
let ploverApp = "/Applications/Plover.app"
let deviceFilter: String = {
    if let i = arguments.firstIndex(of: "--device"), i + 1 < arguments.count { return arguments[i + 1] }
    return "Corne"
}()

// The web view covers the whole window, title bar included, and swallows the mouse there.
// This strip sits over its top edge so the window can be dragged by it.
final class DragStrip: NSView {
    override func mouseDown(with event: NSEvent) { window?.performDrag(with: event) }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

final class Viewer: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    var window: NSPanel!
    var web: WKWebView!
    var manager: IOHIDManager!
    var pageReady = false
    var status = ""
    var connected = Set<String>()
    var paneOpen = false     // the window is currently widened for the steno pane
    var paneWanted = false   // the page is on the Steno layer and has asked for it
    let stripHeight: CGFloat = 30   // the page leaves this much clear at the top when live
    var xBeforePane: CGFloat?
    let paneWidth: CGFloat = 336   // the page's steno pane plus its gap
    var stenoOn = false
    var ploverNote = ""
    let ploverQueue = DispatchQueue(label: "plover")

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMenu()
        buildWindow()
        listen()
        // start from a known state: the keyboard is normally on its base layer
        if managePlover { plover(on: false) }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { true }

    func buildMenu() {
        let main = NSMenu(), appItem = NSMenuItem(), appMenu = NSMenu()
        appMenu.addItem(withTitle: "Quit Corne Layers", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        main.addItem(appItem)

        let windowItem = NSMenuItem(), windowMenu = NSMenu(title: "Window")
        miniItem = windowMenu.addItem(withTitle: "Mini Player", action: #selector(toggleMini), keyEquivalent: "M")   // ⇧⌘M
        topItem = windowMenu.addItem(withTitle: "Keep Mini Player on Top", action: #selector(toggleOnTop), keyEquivalent: "")
        windowMenu.addItem(.separator())
        windowMenu.addItem(withTitle: "Minimize", action: #selector(minimize), keyEquivalent: "m")
        for item in windowMenu.items { item.target = self }
        windowItem.submenu = windowMenu
        main.addItem(windowItem)
        NSApp.mainMenu = main
    }

    // MARK: Window modes

    // Full size, or a mini player: a small window with only the board (and, on Steno, the
    // stroke), which floats over other apps unless that is switched off. Each mode keeps
    // its own size and place.
    let defaults = UserDefaults.standard
    var mini = false
    var miniButton: NSButton!
    var miniItem: NSMenuItem!
    var topItem: NSMenuItem!
    var miniOnTop: Bool { defaults.object(forKey: "miniOnTop") as? Bool ?? true }
    let sizes = (full: NSSize(width: 980, height: 500), mini: NSSize(width: 600, height: 300))
    let smallest = (full: NSSize(width: 760, height: 400), mini: NSSize(width: 300, height: 150))

    func frameKey(_ mini: Bool) -> String { mini ? "frame.mini" : "frame.full" }

    func rememberFrame() {
        var frame = window.frame
        if !mini && paneOpen {   // remembered at its width without the steno pane
            frame.size.width -= paneWidth
            if let x = xBeforePane { frame.origin.x = x }
        }
        defaults.set(NSStringFromRect(frame), forKey: frameKey(mini))
    }

    func windowDidMove(_ note: Notification) { rememberFrame() }
    func windowDidEndLiveResize(_ note: Notification) { rememberFrame() }

    @objc func minimize() { window.miniaturize(nil) }

    @objc func toggleOnTop() {
        defaults.set(!miniOnTop, forKey: "miniOnTop")
        applyMode(animate: false, move: false)
    }

    @objc func toggleMini() {
        rememberFrame()
        mini.toggle()
        defaults.set(mini, forKey: "mini")
        // each mode's remembered frame is without the pane; it is added back below if wanted
        paneOpen = false
        xBeforePane = nil
        applyMode(animate: true, move: true)
        fitPane()
    }

    func applyMode(animate: Bool, move: Bool) {
        window.contentMinSize = mini ? smallest.mini : smallest.full
        if move {
            var frame = defaults.string(forKey: frameKey(mini)).map(NSRectFromString) ?? .zero
            if frame.width < 1 || !NSScreen.screens.contains(where: { $0.visibleFrame.intersects(frame) }) {
                // nowhere remembered: this mode's usual size, keeping the top left corner in place
                let size = window.frameRect(forContentRect: NSRect(origin: .zero, size: mini ? sizes.mini : sizes.full)).size
                frame = NSRect(x: window.frame.minX, y: window.frame.maxY - size.height, width: size.width, height: size.height)
            }
            window.setFrame(frame, display: true, animate: animate)
        }
        window.level = mini && miniOnTop ? .floating : .normal
        miniButton.image = NSImage(systemSymbolName: mini ? "pip.exit" : "pip.enter", accessibilityDescription: nil)
        miniButton.toolTip = mini ? "Full size" : "Mini player"
        miniItem.state = mini ? .on : .off
        topItem.state = miniOnTop ? .on : .off
        js("window.live.mini(\(mini))")
    }

    func buildWindow() {
        // a panel that never takes keyboard focus
        window = NSPanel(contentRect: NSRect(origin: .zero, size: sizes.full),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable, .nonactivatingPanel, .fullSizeContentView],
                         backing: .buffered, defer: false)
        window.title = "Corne Layers"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.isMovableByWindowBackground = true
        window.hidesOnDeactivate = false
        window.becomesKeyOnlyIfNeeded = true
        window.backgroundColor = NSColor(red: 0x11 / 255, green: 0x13 / 255, blue: 0x18 / 255, alpha: 1)
        window.appearance = NSAppearance(named: .darkAqua)
        window.center()
        // the yellow button's own action does nothing on a panel that can't become main
        let yellow = window.standardWindowButton(.miniaturizeButton)
        yellow?.target = self
        yellow?.action = #selector(minimize)

        // the mini player button, at the right of the title bar
        miniButton = NSButton(image: NSImage(systemSymbolName: "pip.enter", accessibilityDescription: nil)!,
                              target: self, action: #selector(toggleMini))
        miniButton.isBordered = false
        miniButton.contentTintColor = .secondaryLabelColor
        miniButton.frame = NSRect(x: 0, y: 0, width: 36, height: 28)
        let accessory = NSTitlebarAccessoryViewController()
        accessory.view = miniButton
        accessory.layoutAttribute = .trailing
        window.addTitlebarAccessoryViewController(accessory)

        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(self, name: "layer")
        configuration.userContentController.add(self, name: "lookup")
        configuration.userContentController.add(self, name: "pane")
        web = WKWebView(frame: window.contentLayoutRect, configuration: configuration)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        web.setValue(false, forKey: "drawsBackground")
        window.contentView = web
        let bounds = web.bounds
        let strip = DragStrip(frame: NSRect(x: 0, y: bounds.height - stripHeight, width: bounds.width, height: stripHeight))
        strip.autoresizingMask = [.width, .minYMargin]
        web.addSubview(strip)
        if let page = Bundle.main.url(forResource: "corne-keymap", withExtension: "html") {
            web.loadFileURL(page, allowingReadAccessTo: page.deletingLastPathComponent())
        }
        mini = defaults.bool(forKey: "mini")
        applyMode(animate: false, move: true)
        window.delegate = self   // from here on, moves and resizes are remembered
        window.orderFrontRegardless()
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        pageReady = true
        say(status)
        js("window.live.mini(\(mini))")
    }

    func js(_ source: String) {
        if pageReady { web.evaluateJavaScript(source, completionHandler: nil) }
    }

    func say(_ text: String) {
        status = text
        if logging { print("status: \(text)") }
        let quoted = String(data: try! JSONEncoder().encode(text), encoding: .utf8)!
        js("window.live.status(\(quoted))")
    }

    // MARK: Plover

    // the page reports each layer signal from the keyboard
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        if message.name == "lookup" { return lookup(message.body) }
        if message.name == "pane" { return pane(open: message.body as? Bool ?? false) }
        guard managePlover, let layer = message.body as? String else { return }
        let on = layer == stenoLayer
        if on != stenoOn {
            stenoOn = on
            plover(on: on)
        }
    }

    func run(_ path: String, _ args: [String]) -> Int32 {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: path)
        process.arguments = args
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        do { try process.run() } catch { return -1 }
        process.waitUntilExit()
        return process.terminationStatus
    }

    func plover(on: Bool) {
        ploverQueue.async {
            let binary = ploverApp + "/Contents/MacOS/Plover"
            guard FileManager.default.isExecutableFile(atPath: binary) else { return }
            var running = self.run("/usr/bin/pgrep", ["-x", "Plover"]) == 0
            if !running && !on { return }
            if !running { _ = self.run("/usr/bin/open", ["-gj", ploverApp]) }
            // a Plover that was just started takes a few seconds to accept commands
            var sent = false
            for _ in 0..<40 {
                running = self.run("/usr/bin/pgrep", ["-x", "Plover"]) == 0
                if running && self.run(binary, ["-s", "plover_send_command", on ? "resume" : "suspend"]) == 0 { sent = true; break }
                Thread.sleep(forTimeInterval: 0.5)
            }
            if logging { print("plover \(on ? "resume" : "suspend"): \(sent ? "sent" : "failed")") }
            DispatchQueue.main.async {
                self.ploverNote = sent ? (on ? " Plover is on." : " Plover is off.") : " Couldn't reach Plover."
                if !self.connected.isEmpty { self.sayConnection() }
            }
        }
    }

    // MARK: Steno pane

    // The page's steno pane sits to the right of the board. Widen the window by its width
    // rather than squeezing the board, moving left only if there's no room on screen.
    func pane(open: Bool) {
        paneWanted = open
        fitPane()
        js("window.live.paneDone()")
    }

    // the window is wider by the pane only at full size; the mini player has no pane
    func fitPane() {
        let open = paneWanted && !mini
        guard open != paneOpen else { return }
        paneOpen = open
        var frame = window.frame
        frame.size.width += open ? paneWidth : -paneWidth
        if open {
            xBeforePane = nil
            if let screen = window.screen?.visibleFrame, frame.maxX > screen.maxX {
                xBeforePane = frame.origin.x
                frame.origin.x = max(screen.minX, screen.maxX - frame.width)
            }
        } else if let x = xBeforePane {
            frame.origin.x = x
            xBeforePane = nil
        }
        window.setFrame(frame, display: true, animate: true)
    }

    func applicationWillTerminate(_ note: Notification) {
        rememberFrame()
    }

    // MARK: Steno dictionaries

    // Plover's default dictionaries, highest priority first
    lazy var dictionaries: [[String: String]] = ["user.json", "commands.json", "main.json"].compactMap { name in
        let folder = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/plover")
        guard let data = try? Data(contentsOf: folder.appendingPathComponent(name)) else { return nil }
        return (try? JSONSerialization.jsonObject(with: data)) as? [String: String]
    }

    // the page sends the last few strokes; answer with the longest run ending at the newest
    // one that has an entry, the way a multi-stroke word would resolve
    func lookup(_ body: Any) {
        guard let request = body as? [String: Any], let id = request["id"] as? Int,
              let strokes = request["strokes"] as? [String], !strokes.isEmpty else { return }
        for count in stride(from: strokes.count, through: 1, by: -1) {
            let outline = strokes.suffix(count).joined(separator: "/")
            if let text = dictionaries.lazy.compactMap({ $0[outline] }).first {
                let quoted = String(data: try! JSONEncoder().encode(text), encoding: .utf8)!
                return js("window.live.translation(\(id), \(quoted), \(count))")
            }
        }
        js("window.live.translation(\(id), null, 1)")
    }

    // MARK: HID

    func listen() {
        manager = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
        let matching: [[String: Int]] = [
            [kIOHIDDeviceUsagePageKey: kHIDPage_GenericDesktop, kIOHIDDeviceUsageKey: kHIDUsage_GD_Keyboard],
            [kIOHIDDeviceUsagePageKey: kHIDPage_Consumer, kIOHIDDeviceUsageKey: kHIDUsage_Csmr_ConsumerControl],
        ]
        IOHIDManagerSetDeviceMatchingMultiple(manager, matching as CFArray)
        let me = Unmanaged.passUnretained(self).toOpaque()

        IOHIDManagerRegisterDeviceMatchingCallback(manager, { context, _, _, device in
            Unmanaged<Viewer>.fromOpaque(context!).takeUnretainedValue().device(device, arrived: true)
        }, me)
        IOHIDManagerRegisterDeviceRemovalCallback(manager, { context, _, _, device in
            Unmanaged<Viewer>.fromOpaque(context!).takeUnretainedValue().device(device, arrived: false)
        }, me)
        IOHIDManagerRegisterInputValueCallback(manager, { context, _, _, value in
            Unmanaged<Viewer>.fromOpaque(context!).takeUnretainedValue().input(value)
        }, me)
        IOHIDManagerScheduleWithRunLoop(manager, CFRunLoopGetMain(), CFRunLoopMode.commonModes.rawValue)

        if IOHIDCheckAccess(kIOHIDRequestTypeListenEvent) != kIOHIDAccessTypeGranted {
            IOHIDRequestAccess(kIOHIDRequestTypeListenEvent)
        }
        let result = IOHIDManagerOpen(manager, IOOptionBits(kIOHIDOptionsTypeNone))
        // the open can fail for one device (e.g. one Karabiner holds exclusively) while
        // the rest still deliver, so only the permission decides what to tell the user
        if logging { print(String(format: "open: %08x, access: %d", result, IOHIDCheckAccess(kIOHIDRequestTypeListenEvent).rawValue)) }
        if IOHIDCheckAccess(kIOHIDRequestTypeListenEvent) != kIOHIDAccessTypeGranted {
            say("Can't read the keyboard yet. Allow Corne Layers in System Settings › Privacy & Security › Input Monitoring, then reopen it.")
        } else {
            sayConnection()
        }
    }

    func name(of device: IOHIDDevice) -> String {
        IOHIDDeviceGetProperty(device, kIOHIDProductKey as CFString) as? String ?? ""
    }

    func wanted(_ device: IOHIDDevice) -> Bool {
        deviceFilter.isEmpty || name(of: device).range(of: deviceFilter, options: .caseInsensitive) != nil
    }

    func device(_ device: IOHIDDevice, arrived: Bool) {
        if logging { print("\(arrived ? "found" : "lost"): \(name(of: device))") }
        guard wanted(device) else { return }
        if arrived { connected.insert(name(of: device)) } else { connected.remove(name(of: device)) }
        if IOHIDCheckAccess(kIOHIDRequestTypeListenEvent) == kIOHIDAccessTypeGranted { sayConnection() }
    }

    func sayConnection() {
        let what = deviceFilter.isEmpty ? "a keyboard" : "the \(deviceFilter)"
        say(connected.isEmpty ? "Waiting for \(what) to connect." : "Live from \(connected.sorted().joined(separator: ", ")).\(ploverNote)")
    }

    func input(_ value: IOHIDValue) {
        let element = IOHIDValueGetElement(value)
        guard wanted(IOHIDElementGetDevice(element)) else { return }
        let page = Int(IOHIDElementGetUsagePage(element))
        let usage = Int(IOHIDElementGetUsage(element))
        let number = IOHIDValueGetIntegerValue(value)
        if logging { print(String(format: "page %02x usage %04x value %d", page, usage, number)) }
        guard page == kHIDPage_KeyboardOrKeypad || page == kHIDPage_Consumer else { return }
        js("window.live.hid(\(page), \(usage), \(number))")
    }
}

setvbuf(stdout, nil, _IOLBF, 0)
let app = NSApplication.shared
let viewer = Viewer()
app.delegate = viewer
app.setActivationPolicy(.regular)
app.run()
