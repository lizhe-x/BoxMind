@preconcurrency import AVFoundation
import SwiftUI

/// Back camera for photo intake: live preview + one JPEG per shutter press.
/// Replaces the web `getUserMedia` + canvas capture.
@MainActor
@Observable
final class CameraController: NSObject {
    nonisolated(unsafe) let session = AVCaptureSession()
    nonisolated(unsafe) private let output = AVCapturePhotoOutput()
    private let queue = DispatchQueue(label: "me.boxmind.camera")
    private(set) var ready = false
    /// No camera (simulator), or permission denied.
    private(set) var unavailable = false
    private var configured = false
    private var pending: CheckedContinuation<Data?, Never>?

    func start() async {
        #if targetEnvironment(simulator)
        unavailable = true
        #else
        guard await AVCaptureDevice.requestAccess(for: .video) else {
            unavailable = true
            return
        }
        nonisolated(unsafe) let session = session
        nonisolated(unsafe) let output = output
        let configured = configured
        let ok: Bool = await withCheckedContinuation { c in
            queue.async {
                if !configured {
                    session.beginConfiguration()
                    session.sessionPreset = .photo
                    guard let dev = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
                          let input = try? AVCaptureDeviceInput(device: dev),
                          session.canAddInput(input), session.canAddOutput(output) else {
                        session.commitConfiguration()
                        c.resume(returning: false)
                        return
                    }
                    session.addInput(input)
                    session.addOutput(output)
                    if let conn = output.connection(with: .video), conn.isVideoRotationAngleSupported(90) {
                        conn.videoRotationAngle = 90 // portrait-only app
                    }
                    session.commitConfiguration()
                }
                session.startRunning()
                c.resume(returning: true)
            }
        }
        self.configured = ok
        ready = ok
        unavailable = !ok
        #endif
    }

    func stop() {
        nonisolated(unsafe) let session = session
        queue.async { if session.isRunning { session.stopRunning() } }
    }

    /// One full-resolution JPEG (EXIF orientation set), or nil when the camera is not running.
    func capture() async -> Data? {
        guard ready, pending == nil else { return nil }
        return await withCheckedContinuation { c in
            pending = c
            let settings: AVCapturePhotoSettings
            if output.availablePhotoCodecTypes.contains(.jpeg) {
                settings = AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg])
            } else {
                settings = AVCapturePhotoSettings()
            }
            output.capturePhoto(with: settings, delegate: self)
        }
    }
}

extension CameraController: AVCapturePhotoCaptureDelegate {
    nonisolated func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        let data = error == nil ? photo.fileDataRepresentation() : nil
        Task { @MainActor in
            self.pending?.resume(returning: data)
            self.pending = nil
        }
    }
}

/// Live preview layer bound to the controller's session.
struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }

    func makeUIView(context: Context) -> PreviewView {
        let v = PreviewView()
        v.previewLayer.session = session
        v.previewLayer.videoGravity = .resizeAspectFill
        if let conn = v.previewLayer.connection, conn.isVideoRotationAngleSupported(90) {
            conn.videoRotationAngle = 90
        }
        return v
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {}
}
