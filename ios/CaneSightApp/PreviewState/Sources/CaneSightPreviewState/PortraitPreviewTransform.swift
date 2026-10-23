#if canImport(CoreGraphics)
import CoreGraphics
import Foundation

/// ARKit normalized top-left coordinates to CoreImage pixel coordinates.
/// Kept separate so rendered pixel-marker tests exercise the production path.
public enum PortraitPreviewTransform {
    public enum GeometryError: Error { case invalid }
    public static func pixels(imageWidth w: Double, imageHeight h: Double,
        previewWidth pw: Double, previewHeight ph: Double, normalized t: CGAffineTransform) throws -> CGAffineTransform {
        guard [w, h, pw, ph].allSatisfy({ $0.isFinite && $0 > 0 }),
              [t.a,t.b,t.c,t.d,t.tx,t.ty].allSatisfy({ $0.isFinite }) else { throw GeometryError.invalid }
        return CGAffineTransform(a: pw*t.a/w, b: -ph*t.b/w,
            c: -pw*t.c/h, d: ph*t.d/h, tx: pw*(t.c+t.tx), ty: ph*(1-t.d-t.ty))
    }
}
#endif
