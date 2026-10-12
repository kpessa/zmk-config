// Corne Layers: a small floating window that shows the layer page live.
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

final class Viewer: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    var window: NSPanel!
    var web: WKWebView!
    var manager: IOHIDManager!
    var pageReady = false
    var status = ""
    var connected = Set<String>()
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
        NSApp.mainMenu = main
    }

    func buildWindow() {
        // a panel that floats over other apps and never takes keyboard focus
        window = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 820, height: 532),
                         styleMask: [.titled, .closable, .resizable, .nonactivatingPanel, .fullSizeContentView],
                         backing: .buffered, defer: false)
        window.title = "Corne Layers"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.isMovableByWindowBackground = true
        window.level = .floating
        window.hidesOnDeactivate = false
        window.becomesKeyOnlyIfNeeded = true
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        window.backgroundColor = NSColor(red: 0x11 / 255, green: 0x13 / 255, blue: 0x18 / 255, alpha: 1)
        window.appearance = NSAppearance(named: .darkAqua)
        window.contentAspectRatio = NSSize(width: 820, height: 532)
        window.setFrameAutosaveName("CorneLayers")
        if window.frame.origin == .zero { window.center() }

        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(self, name: "layer")
        web = WKWebView(frame: window.contentLayoutRect, configuration: configuration)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        web.setValue(false, forKey: "drawsBackground")
        window.contentView = web
        if let page = Bundle.main.url(forResource: "corne-keymap", withExtension: "html") {
            web.loadFileURL(page, allowingReadAccessTo: page.deletingLastPathComponent())
        }
        window.orderFrontRegardless()
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        pageReady = true
        say(status)
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
