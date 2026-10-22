import ImageIO
import UIKit
import BoxMindKit

/// Upload-size images. Port of frontend/src/image.ts: longest edge ≤ 1600, JPEG 0.82, EXIF orientation baked in
/// (so HEIC from the library and rotated camera shots arrive upright at the vision model).
enum ImageResize {
    static func jpeg(_ data: Data, maxEdge: CGFloat = 1600, quality: CGFloat = 0.82) -> Data? {
        guard let src = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        let opts: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true, // apply orientation
            kCGImageSourceThumbnailMaxPixelSize: maxEdge,     // never upscales
            kCGImageSourceShouldCacheImmediately: true,
        ]
        guard let cg = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary) else { return nil }
        return UIImage(cgImage: cg).jpegData(compressionQuality: quality)
    }

    static func clip(_ data: Data) -> PhotoClip? {
        jpeg(data).map { PhotoClip(data: $0) }
    }

    #if DEBUG
    /// Stand-in shot for the simulator (no camera): a kraft-coloured rectangle with a "box".
    static func placeholderClip() -> PhotoClip {
        let size = CGSize(width: 640, height: 480)
        let img = UIGraphicsImageRenderer(size: size).image { ctx in
            UIColor(red: 0.09, green: 0.1, blue: 0.14, alpha: 1).setFill()
            ctx.fill(CGRect(origin: .zero, size: size))
            UIColor(red: 0.61, green: 0.48, blue: 0.32, alpha: 1).setFill()
            UIBezierPath(roundedRect: CGRect(x: 120, y: 110, width: 400, height: 260), cornerRadius: 12).fill()
        }
        return PhotoClip(data: img.jpegData(compressionQuality: 0.8) ?? Data())
    }
    #endif
}
