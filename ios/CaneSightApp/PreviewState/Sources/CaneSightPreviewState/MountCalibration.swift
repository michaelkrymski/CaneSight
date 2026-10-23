import Foundation
import simd

public struct MountRegion: Codable, Equatable, Sendable {
    public var y: Float
    public var height: Float
    public var x: Float { 0 }
    public static let width: Float = 1
    public static let defaultHeight: Float = 1/8
    public init(y: Float=3/8,height: Float=Self.defaultHeight) {
        self.height=max(Self.defaultHeight,min(1,height))
        self.y=max(0,min(1-self.height,y))
    }
    public var valid: Bool { y.isFinite && height.isFinite && height>=Self.defaultHeight && height<=1 && y>=0 && y+height<=1.00001 }
}

public struct MountCamera: Codable, Equatable, Sendable {
    public let device: String
    public let imageWidth, imageHeight, depthWidth, depthHeight: Int
    /// fx,fy,cx,cy normalized to original camera image, before portrait display mapping.
    public let k: [Float]
    /// ARKit image-normalized -> portrait viewport-normalized affine transform.
    public let display: [Float]
    public init(device: String,imageWidth: Int,imageHeight: Int,depthWidth: Int,depthHeight: Int,k: [Float],display: [Float]) {
        self.device=device;self.imageWidth=imageWidth;self.imageHeight=imageHeight
        self.depthWidth=depthWidth;self.depthHeight=depthHeight;self.k=k;self.display=display
    }
    public var valid: Bool {
        !device.isEmpty && imageWidth>0 && imageHeight>0 && depthWidth>0 && depthHeight>0 &&
        k.count==4 && k.allSatisfy(\.isFinite) && k[0]>0 && k[1]>0 &&
        display.count==6 && display.allSatisfy(\.isFinite) && display[0]*display[3]-display[1]*display[2]>0.001
    }
    public func compatible(with other: Self) -> Bool {
        guard valid,other.valid,device==other.device,imageWidth==other.imageWidth,imageHeight==other.imageHeight,
              depthWidth==other.depthWidth,depthHeight==other.depthHeight else { return false }
        return zip(k,other.k).allSatisfy { abs($0-$1)<=0.03*max(abs($0),0.1) } &&
            zip(display,other.display).allSatisfy { abs($0-$1)<0.001 }
    }
    public func viewport(_ p: SIMD3<Float>) -> SIMD2<Float>? {
        guard valid, p.z < -0.001 else { return nil }
        let u=p.x/(-p.z)*k[0]+k[2],v = -p.y/(-p.z)*k[1]+k[3]
        return SIMD2(display[0]*u+display[2]*v+display[4],display[1]*u+display[3]*v+display[5])
    }
    public func ray(_ viewport: SIMD2<Float>) -> SIMD3<Float> {
        let d=display,det=d[0]*d[3]-d[1]*d[2],x=viewport.x-d[4],y=viewport.y-d[5]
        let u=(d[3]*x-d[2]*y)/det,v=(-d[1]*x+d[0]*y)/det
        return SIMD3((u-k[2])/k[0],-(v-k[3])/k[1],-1)
    }
}

public struct MountProfile: Codable, Equatable, Sendable {
    public var version=2
    public var orientation="portrait-rear"
    public var coordinateConvention="camera-minus-Z-forward;level-Y-up;yaw-follows-cane"
    public var pitchLimitDegrees: Float=15
    public var rollLimitDegrees: Float=10
    public var heightLimitMetres: Float=0.10
    public var floorBandHalfwidthMetres: Float=0.02
    public var minimumRangeMetres: Float=0.25
    public var maximumRangeMetres: Float=4
    public let id: UUID
    public var confirmedAt: Date
    public var helperConfirmed=false
    public var verifiedSides=[false,false,false]
    public var lowObstacleVerified=false
    public let camera: MountCamera
    public let region: MountRegion
    /// Camera -> yaw-following, gravity-level frame (+X right,+Y up,-Z forward).
    /// Contains no ARKit world origin/anchor and is reusable after tracking reset.
    public let neutralColumns: [Float]
    public let cameraHeight: Float
    public let floorUncertainty: Float
    public let minimumLowObstacleHeight: Float
    public init(camera: MountCamera,region: MountRegion,neutral: simd_float3x3,cameraHeight: Float) {
        id=UUID();confirmedAt=Date();self.camera=camera;self.region=region
        neutralColumns=(0..<3).flatMap { c in (0..<3).map { neutral[c][$0] } }
        self.cameraHeight=cameraHeight;floorUncertainty=0.03;minimumLowObstacleHeight=0.08
    }
    public var neutral: simd_float3x3 {
        simd_float3x3(columns:(SIMD3(neutralColumns[0],neutralColumns[1],neutralColumns[2]),
            SIMD3(neutralColumns[3],neutralColumns[4],neutralColumns[5]),SIMD3(neutralColumns[6],neutralColumns[7],neutralColumns[8])))
    }
    public var valid: Bool {
        guard version==2,orientation=="portrait-rear",
              coordinateConvention=="camera-minus-Z-forward;level-Y-up;yaw-follows-cane",
              pitchLimitDegrees==15,rollLimitDegrees==10,heightLimitMetres==0.10,
              floorBandHalfwidthMetres==0.02,minimumRangeMetres==0.25,maximumRangeMetres==4,
              camera.valid,region.valid,neutralColumns.count==9,neutralColumns.allSatisfy(\.isFinite),
              cameraHeight.isFinite,cameraHeight>=0.3,cameraHeight<=2,
              floorUncertainty==0.03,minimumLowObstacleHeight==0.08 else { return false }
        let n=neutral
        return abs(simd_determinant(n)-1)<0.001 && (0..<3).allSatisfy { i in
            (0..<3).allSatisfy { j in abs(simd_dot(n[i],n[j])-(i==j ? 1:0))<0.001 }
        }
    }
    public var readyForReuse: Bool { valid && helperConfirmed && verifiedSides == [true,true,true] && lowObstacleVerified }
    public func data() throws -> Data { try JSONEncoder().encode(self) }
    public static func load(_ data: Data) throws -> Self {
        guard data.count<=8192 else { throw CalibrationError.incompatible }
        let profile=try JSONDecoder().decode(Self.self,from:data)
        guard profile.readyForReuse else { throw CalibrationError.incompatible };return profile
    }
}
public enum CalibrationError: Error, Equatable { case incompatible,pose,floor,height,angle,outOfView }

public enum CalibratedMountGeometry {
    /// Remove world yaw while preserving gravity pitch/roll. No integrated gyro.
    public static func cameraToLevel(_ cameraToWorld: simd_float3x3) -> simd_float3x3? {
        guard (0..<3).allSatisfy({ c in (0..<3).allSatisfy { cameraToWorld[c][$0].isFinite } }) else { return nil }
        let forward = -cameraToWorld.columns.2
        let horizontal=SIMD3<Float>(forward.x,0,forward.z)
        guard simd_length(horizontal)>0.2 else { return nil }
        let back = -simd_normalize(horizontal),up=SIMD3<Float>(0,1,0),right=simd_cross(up,back)
        return simd_transpose(simd_float3x3(columns:(right,up,back)))*cameraToWorld
    }
    private static func angles(_ pose: simd_float3x3,camera: MountCamera) -> SIMD2<Float> {
        let f=pose*SIMD3<Float>(0,0,-1)
        let right=simd_normalize(pose*(camera.ray([0.6,0.5])-camera.ray([0.4,0.5])))
        return SIMD2(atan2(f.y,sqrt(f.x*f.x+f.z*f.z)),atan2(right.y,right.x))
    }
    public static func validate(_ profile: MountProfile,camera: MountCamera,pose: simd_float3x3,height: Float?) throws {
        guard profile.valid,profile.camera.compatible(with:camera) else { throw CalibrationError.incompatible }
        guard let height,height.isFinite else { throw CalibrationError.floor }
        guard abs(height-profile.cameraHeight)<=0.10 else { throw CalibrationError.height }
        let a=angles(pose,camera:camera),n=angles(profile.neutral,camera:profile.camera)
        let roll=atan2(sin(a.y-n.y),cos(a.y-n.y))
        guard a.x.isFinite,roll.isFinite,abs(a.x-n.x)<=15 * .pi/180,abs(roll)<=10 * .pi/180 else { throw CalibrationError.angle }
        let visible=try visibility(profile,camera:camera,pose:pose)
        guard visible.contains(true) else { throw CalibrationError.outOfView }
    }
    /// Four corners of each actual sector's projected physical ray frustum.
    public static func projection(_ profile: MountProfile,camera: MountCamera,pose: simd_float3x3) throws -> [[SIMD2<Float>]] {
        guard profile.valid,camera.valid else { throw CalibrationError.incompatible }
        let r=profile.region,toCurrent=simd_transpose(pose)*profile.neutral
        return try (0..<3).map { sector in
            let x0=r.x+MountRegion.width*Float(sector)/3,x1=r.x+MountRegion.width*Float(sector+1)/3
            return try [SIMD2(x0,r.y),SIMD2(x1,r.y),SIMD2(x1,r.y+r.height),SIMD2(x0,r.y+r.height)].map { corner in
                guard let p=camera.viewport(toCurrent*profile.camera.ray(corner)),p.x.isFinite,p.y.isFinite,
                      abs(p.x)<=10,abs(p.y)<=10 else { throw CalibrationError.outOfView }
                return p
            }
        }
    }
    public static func visibility(_ profile: MountProfile,camera: MountCamera,pose: simd_float3x3) throws -> [Bool] {
        try projection(profile,camera:camera,pose:pose).map { corners in
            corners.allSatisfy { $0.x>=(-0.00001) && $0.x<=1.00001 && $0.y>=(-0.00001) && $0.y<=1.00001 }
        }
    }
    public struct Selection: Sendable {
        public var metres=[[Float](),[Float](),[Float]()]
        public var confidence=[[UInt8](),[UInt8](),[UInt8]()]
        public var lowObstacleHighPixels=0
        public var quality=[[String:Int](),[String:Int](),[String:Int]()]
        /// Bounded display markers: u,v and exclusion code (1 confidence,2 floor).
        public var exclusions=[[Float]]()
    }
    public struct PackedSamples: Sendable {
        public let width,height,denominator: Int
        public let metres: [Float]
        public let confidence: [UInt8]
    }
    /// Bounded 2D tiles per sector, rather than an unbounded one-pixel column.
    /// Every original selected sample is placed once; unused slots stay NaN.
    public static func pack(_ selected: Selection,maximumDimension: Int=2048,maximumPixels: Int=262144) -> PackedSamples? {
        guard selected.metres.count==3,selected.confidence.count==3,
              (0..<3).allSatisfy({ selected.metres[$0].count==selected.confidence[$0].count }) else { return nil }
        let count=selected.metres.map(\.count).max() ?? 0
        guard count>0,count<=maximumPixels,maximumDimension>=3 else { return nil }
        let stride=min(32,min(count,maximumDimension/3)),width=stride*3,height=(count+stride-1)/stride
        guard height<=maximumDimension,height<=maximumPixels/width else { return nil }
        var metres=[Float](repeating:.nan,count:width*height),confidence=[UInt8](repeating:0,count:width*height)
        for sector in 0..<3 { for i in selected.metres[sector].indices {
            let out=(i/stride)*width+sector*stride+i%stride
            metres[out]=selected.metres[sector][i];confidence[out]=selected.confidence[sector][i]
        } }
        return PackedSamples(width:width,height:height,denominator:stride*height,metres:metres,confidence:confidence)
    }
    public static func select(profile: MountProfile,camera: MountCamera,pose: simd_float3x3,
        metres: [Float],confidence: [UInt8],floorIndices: Set<Int>,height: Float) -> Selection {
        var result=Selection()
        guard profile.valid,camera.valid,metres.count==camera.depthWidth*camera.depthHeight,
              confidence.count==metres.count else { return result }
        let visible=(try? visibility(profile,camera:camera,pose:pose)) ?? [false,false,false]
        let toNeutral=simd_transpose(profile.neutral)*pose,r=profile.region
        let nk=profile.camera.k,nd=profile.camera.display
        func neutralViewport(_ p: SIMD3<Float>) -> SIMD2<Float>? {
            guard p.z < -0.001 else { return nil }
            let u=p.x/(-p.z)*nk[0]+nk[2],v = -p.y/(-p.z)*nk[1]+nk[3]
            return SIMD2(nd[0]*u+nd[2]*v+nd[4],nd[1]*u+nd[3]*v+nd[5])
        }
        for y in 0..<camera.depthHeight { for x in 0..<camera.depthWidth {
            let i=y*camera.depthWidth+x,z=metres[i]
            // A direction selects the region even when its depth is invalid;
            // unknown samples stay in coverage denominators.
            let ray=SIMD3<Float>((Float(x)/Float(camera.depthWidth)-camera.k[2])/camera.k[0],
                -(Float(y)/Float(camera.depthHeight)-camera.k[3])/camera.k[1],-1)
            guard let uv=neutralViewport(toNeutral*ray),uv.x>=r.x,uv.x<r.x+MountRegion.width,
                  uv.y>=r.y,uv.y<r.y+r.height else { continue }
            let sector=min(2,Int((uv.x-r.x)/MountRegion.width*3)),point=ray*z,range=simd_length(point)
            let floor=floorIndices.contains(i)
            let usable=visible[sector] && z.isFinite && z>0 && range>=0.25 && range<=4 && !floor
            result.quality[sector]["selected",default:0]+=1
            if z.isFinite && z>0 {
                result.quality[sector]["finite_positive",default:0]+=1
                if confidence[i]==2 { result.quality[sector]["high_confidence_positive",default:0]+=1 }
                if z>2 {
                    result.quality[sector]["over_2m_raw",default:0]+=1
                    if confidence[i]==2 { result.quality[sector]["over_2m_high",default:0]+=1 }
                }
                if range<0.25 || range>4 { result.quality[sector]["outside_range",default:0]+=1 }
            }
            if floor { result.quality[sector]["floor_excluded",default:0]+=1 }
            if !visible[sector] { result.quality[sector]["sector_not_visible",default:0]+=1 }
            if usable && confidence[i]==2 { result.quality[sector]["usable_high",default:0]+=1 }
            result.metres[sector].append(usable ? range : .nan)
            result.confidence[sector].append(visible[sector] ? confidence[i] : 0)
            if usable,confidence[i]==2 {
                let aboveFloor=height+(pose*point).y
                if aboveFloor>=profile.minimumLowObstacleHeight && aboveFloor<=0.20 { result.lowObstacleHighPixels+=1 }
            }
            if result.exclusions.count<120,(floor || confidence[i] != 2),let view=camera.viewport(ray) {
                result.exclusions.append([view.x,view.y,floor ? 2:1])
            }
        } }
        return result
    }
}

/// A small stable, increasing-source-time window. Reset on loss/epoch change.
public struct StableMountWindow: Sendable {
    public private(set) var count=0
    private var start: Double?
    private var last: Double?
    private var firstPose: simd_float3x3?
    private var firstHeight: Float?
    public init() {}
    public mutating func reset() { self=Self() }
    public mutating func observe(timestamp: Double,now: Double?=nil,pose: simd_float3x3,height: Float,usable: Bool) -> Bool {
        if let now,(!now.isFinite || now<timestamp || now-timestamp>=0.5) { reset();return false }
        guard timestamp.isFinite,usable,height.isFinite,last.map({ timestamp>$0 && timestamp-$0<0.5 }) ?? true else { reset();return false }
        if let p=firstPose,let h=firstHeight {
            let relative=simd_transpose(p)*pose
            let cosine=max(-1,min(1,(relative.columns.0.x+relative.columns.1.y+relative.columns.2.z-1)/2))
            if acos(cosine)>2 * .pi/180 || abs(height-h)>0.03 { reset();return false }
        } else { firstPose=pose;firstHeight=height;start=timestamp }
        count+=1;last=timestamp
        return count>=12 && timestamp-(start ?? timestamp)>=2.5
    }
}

/// Helper-identified targets, not object recognition or inference about unknown background.
public enum MountTargetEvidence {
    public static func canRecord(target: Int,distances: [Double?]) -> Bool {
        guard distances.count==3,(0..<3).contains(target),
              distances.compactMap({ $0 }).allSatisfy({ $0.isFinite && $0>0 }),
              let placed=distances[target] else { return false }
        return distances.enumerated().filter { $0.offset != target }.allSatisfy { item in
            guard let known=item.element else { return true } // no evidence about this background
            return placed+0.15<=known
        }
    }
}
