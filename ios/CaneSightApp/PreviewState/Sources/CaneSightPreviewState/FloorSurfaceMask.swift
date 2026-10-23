import Foundation
import simd

/// Geometric exclusion only: never treats missing depth as free space.
/// Callers supply current, confidently classified floor planes, not a screen crop.
public enum FloorSurfaceMask {
    public struct Plane: Sendable {
        public let cameraToPlane: simd_float4x4
        public let boundary: [SIMD2<Float>]
        public init(cameraToPlane: simd_float4x4, boundary: [SIMD2<Float>]) {
            self.cameraToPlane=cameraToPlane; self.boundary=boundary
        }
    }
    public static func contains(_ point: SIMD2<Float>, boundary: [SIMD2<Float>], inset: Float=0.05) -> Bool {
        guard boundary.count >= 3, boundary.count <= 256, inset.isFinite, inset >= 0,
              point.x.isFinite, point.y.isFinite,
              boundary.allSatisfy({ $0.x.isFinite && $0.y.isFinite }) else { return false }
        var inside=false
        for i in boundary.indices {
            let a=boundary[i], b=boundary[(i+1)%boundary.count], edge=b-a
            let length=simd_length_squared(edge)
            guard length > 0 else { return false }
            let t=max(0,min(1,simd_dot(point-a,edge)/length))
            if simd_length(point-(a+t*edge)) <= inset { return false }
            if (a.y > point.y) != (b.y > point.y),
               point.x < (b.x-a.x)*(point.y-a.y)/(b.y-a.y)+a.x { inside.toggle() }
        }
        return inside
    }
    /// Intrinsics already scaled to depth dimensions. AR camera has -Z forward,
    /// +Y up; depth pixels have +Y down and positive axial Z depth.
    public static func indices(width: Int, height: Int, metres: [Float], confidence: [UInt8],
        intrinsics k: SIMD4<Float>, planes: [Plane]) -> [Int] {
        guard width > 0, height > 0, width <= 4096, height <= 4096,
              metres.count == width*height, confidence.count == metres.count,
              [k.x,k.y,k.z,k.w].allSatisfy({ $0.isFinite }), k.x > 0, k.y > 0,
              !planes.isEmpty, planes.count <= 8 else { return [] }
        let validPlanes=planes.filter { plane in
            (0..<4).allSatisfy { c in (0..<4).allSatisfy { r in plane.cameraToPlane[c][r].isFinite } }
        }
        var excluded=[Int]()
        for y in 0..<height { for x in 0..<width {
            let i=y*width+x, z=metres[i]
            guard confidence[i] == 2, z.isFinite, z > 0 else { continue }
            let camera=SIMD4<Float>((Float(x)-k.z)*z/k.x,-(Float(y)-k.w)*z/k.y,-z,1)
            for plane in validPlanes {
                let local=plane.cameraToPlane*camera
                // Only a 2 cm slab around the observed floor, inside its polygon.
                guard abs(local.y) <= 0.02,
                      contains(SIMD2(local.x,local.z),boundary:plane.boundary) else { continue }
                excluded.append(i); break
            }
        } }
        return excluded
    }
}
