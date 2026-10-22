import SwiftUI
import VisionKit

/// QR / barcode reader built on VisionKit's DataScannerViewController. Replaces @zxing/browser.
/// `onCode` fires once per scan session (the first code seen); set `active` false to pause.
struct BarcodeScanner: UIViewControllerRepresentable {
    var active: Bool
    var onCode: (String) -> Void

    static var isSupported: Bool {
        DataScannerViewController.isSupported && DataScannerViewController.isAvailable
    }

    func makeUIViewController(context: Context) -> ScannerHost {
        ScannerHost(onCode: onCode)
    }

    func updateUIViewController(_ host: ScannerHost, context: Context) {
        host.onCode = onCode
        host.setActive(active)
    }

    @MainActor
    final class ScannerHost: UIViewController, DataScannerViewControllerDelegate {
        var onCode: (String) -> Void
        private var scanner: DataScannerViewController?
        private var active = true
        private var handled = false
        private var appeared = false

        init(onCode: @escaping (String) -> Void) {
            self.onCode = onCode
            super.init(nibName: nil, bundle: nil)
        }

        @available(*, unavailable) required init?(coder: NSCoder) { fatalError() }

        override func viewDidLoad() {
            super.viewDidLoad()
            view.backgroundColor = .black
            guard BarcodeScanner.isSupported else { return }
            let s = DataScannerViewController(
                recognizedDataTypes: [.barcode()], qualityLevel: .balanced, recognizesMultipleItems: false,
                isHighFrameRateTrackingEnabled: false, isPinchToZoomEnabled: true, isGuidanceEnabled: false,
                isHighlightingEnabled: true)
            s.delegate = self
            addChild(s)
            s.view.frame = view.bounds
            s.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            view.addSubview(s.view)
            s.didMove(toParent: self)
            scanner = s
        }

        override func viewDidAppear(_ animated: Bool) {
            super.viewDidAppear(animated)
            appeared = true
            apply()
        }

        override func viewWillDisappear(_ animated: Bool) {
            super.viewWillDisappear(animated)
            appeared = false
            scanner?.stopScanning()
        }

        func setActive(_ on: Bool) {
            if on && !active { handled = false } // a new scan session accepts the next code
            active = on
            apply()
        }

        private func apply() {
            guard let scanner, appeared else { return }
            if active {
                if !scanner.isScanning { try? scanner.startScanning() }
            } else if scanner.isScanning {
                scanner.stopScanning()
            }
        }

        nonisolated func dataScanner(_ dataScanner: DataScannerViewController, didAdd addedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            let codes = addedItems.compactMap { item -> String? in
                if case .barcode(let b) = item { return b.payloadStringValue }
                return nil
            }
            guard let code = codes.first else { return }
            Task { @MainActor in
                guard self.active, !self.handled else { return }
                self.handled = true
                self.scanner?.stopScanning()
                self.onCode(code)
            }
        }
    }
}
