import ARKit
import SwiftUI
import QuartzCore
import CaneSightDepth
import CaneSightDepthARKit
import CaneSightMountMapping
import CaneSightMountMappingARKit
import CaneSightPreviewState

struct CalibratedCameraFrame: @unchecked Sendable {
    var candidate: MountProfile?
    var pose: simd_float3x3?
    var height: Float?
    var summary: DepthSectorSummary?
    var polygons=[[SIMD2<Float>]]()
    var exclusions=[[Float]]()
    var lowPixels=0
    var problem: String?
    var incompatible=false
    var diagnostics=[String:Any]()
}

enum MountFrameProcessor {
    static func process(_ frame: ARFrame,observation: PortraitObservation,profile: MountProfile?,
        region: MountRegion,device: String) -> CalibratedCameraFrame {
        var out=CalibratedCameraFrame()
        guard let depth=frame.sceneDepth,let confidence=depth.confidenceMap,
              let raw=try? DepthPixelBufferReader.copyFrame(depth:depth.depthMap,confidence:confidence,
                captureTimestampSeconds:frame.timestamp,mode:.live,tracking:.normal),let levels=raw.confidence else {
            out.problem="Depth unavailable";return out
        }
        let size=frame.camera.imageResolution,k=frame.camera.intrinsics,t=observation.geometry.mapping
        let camera=MountCamera(device:device,imageWidth:Int(size.width),imageHeight:Int(size.height),
            depthWidth:raw.width,depthHeight:raw.height,
            k:[k.columns.0.x/Float(size.width),k.columns.1.y/Float(size.height),k.columns.2.x/Float(size.width),k.columns.2.y/Float(size.height)],
            display:[Float(t.a),Float(t.b),Float(t.c),Float(t.d),Float(t.tx),Float(t.ty)])
        if let profile,!profile.camera.compatible(with:camera) {
            out.problem="Camera configuration unavailable; saved calibration retained";out.incompatible=true;return out
        }
        let transform=frame.camera.transform
        guard let pose=CalibratedMountGeometry.cameraToLevel(simd_float3x3(columns:(
            SIMD3(transform.columns.0.x,transform.columns.0.y,transform.columns.0.z),
            SIMD3(transform.columns.1.x,transform.columns.1.y,transform.columns.1.z),
            SIMD3(transform.columns.2.x,transform.columns.2.y,transform.columns.2.z)))) else {
            out.problem="Pose outside supported gravity geometry";return out
        }
        out.pose=pose
        let floors=frame.anchors.compactMap { $0 as? ARPlaneAnchor }.filter { plane in
            let height=transform.columns.3.y-plane.transform.columns.3.y
            return plane.alignment == .horizontal && plane.classification == .floor &&
                abs(plane.transform.columns.1.y)>0.9986 && height>=0.3 && height<=2
        }
        let heights=floors.map { transform.columns.3.y-$0.transform.columns.3.y }
        // Ambiguous floor levels (steps/stairs) are outside the initial envelope.
        guard !floors.isEmpty,floors.count<=8,
              let low=heights.min(),let high=heights.max(),high-low<=0.05 else {
            out.problem="Waiting for a fresh, level floor model; slowly scan floor and furniture";return out
        }
        let height=heights.reduce(0,+)/Float(heights.count)
        out.height=height
        let chosen=profile ?? MountProfile(camera:camera,region:region,neutral:pose,cameraHeight:height)
        out.candidate=chosen
        do {
            try CalibratedMountGeometry.validate(chosen,camera:camera,pose:pose,height:height)
            out.polygons=try CalibratedMountGeometry.projection(chosen,camera:camera,pose:pose)
        } catch {
            switch error as? CalibrationError {
            case .height:out.problem="Grip height outside calibrated ±10 cm range"
            case .angle:out.problem="Outside calibrated ±15° pitch / ±10° roll range"
            case .outOfView:out.problem="Selected region is outside the camera view"
            default:out.problem="Unsupported calibration geometry"
            }
            return out
        }
        let planes=floors.map { anchor in
            FloorSurfaceMask.Plane(cameraToPlane:simd_inverse(anchor.transform)*transform,
                boundary:anchor.geometry.boundaryVertices.map { SIMD2<Float>($0.x,$0.z) })
        }
        let started=CACurrentMediaTime()
        let mask=FloorSurfaceMask.indices(width:raw.width,height:raw.height,metres:raw.metres,confidence:levels,
            intrinsics:SIMD4(camera.k[0]*Float(raw.width),camera.k[1]*Float(raw.height),camera.k[2]*Float(raw.width),camera.k[3]*Float(raw.height)),planes:planes)
        var selected=CalibratedMountGeometry.select(profile:chosen,camera:camera,pose:pose,
            metres:raw.metres,confidence:levels,floorIndices:Set(mask),height:height)
        let visible=(try? CalibratedMountGeometry.visibility(chosen,camera:camera,pose:pose)) ?? [false,false,false]
        let fractions=(try? CalibratedMountGeometry.visibleFractions(chosen,camera:camera,pose:pose)) ?? [0,0,0]
        let supported=fractions.map { $0>=CalibratedMountGeometry.minimumVisibleFraction }
        for sector in 0..<3 where !supported[sector] {
            selected.metres[sector]=Array(repeating:.nan,count:selected.metres[sector].count)
            selected.confidence[sector]=Array(repeating:0,count:selected.confidence[sector].count)
        }
        // Low-target evidence requires all sectors to meet the documented visibility envelope.
        out.lowPixels=supported.allSatisfy({ $0 }) ? selected.lowObstacleHighPixels : 0
        out.exclusions=selected.exclusions
        let counts=selected.metres.map(\.count),rows=counts.max() ?? 0
        guard rows>=32 else { out.problem="Too few pixels in selected region";return out }
        guard let packed=CalibratedMountGeometry.pack(selected,maximumDimension:DepthLimits.maximumDimension,
            maximumPixels:DepthLimits.maximumPixels) else { out.problem="Selected region exceeds sample processing budget";return out }
        out.summary=DepthSectorProcessor(configuration:try! DepthSectorConfiguration()).process(
            DepthFrame(width:packed.width,height:packed.height,metres:packed.metres,confidence:packed.confidence,
                captureTimestampSeconds:raw.captureTimestampSeconds,mode:raw.mode,tracking:raw.tracking))
        out.diagnostics=["mask_applied":true,"classified_floor_planes":floors.count,
            "excluded_high_confidence_pixels":mask.count,"selected_sector_pixels":counts,
            "coverage_denominator_per_sector":packed.denominator,"packed_dimensions":[packed.width,packed.height],"summary_reason":out.summary!.reason.rawValue,"processing_ms":(CACurrentMediaTime()-started)*1000,
            "low_obstacle_high_pixels":out.lowPixels,"fully_visible_sectors":visible,"visible_area_fraction":fractions,"supported_sectors":supported,"sector_input_quality":selected.quality,
            "selected_distance_m":out.summary!.sectors.map { $0.distanceMetres.map { $0 as Any } ?? NSNull() }]
        return out
    }
}

@MainActor final class MountCalibrationController: ObservableObject {
    enum Step: String { case idle,position,stable,left,center,right,low,confirm }
    @Published private(set) var profile: MountProfile?
    @Published private(set) var draft: MountProfile?
    @Published private(set) var step: Step = .idle
    @Published private(set) var region=MountRegion()
    @Published private(set) var message="Calibration required · sighted helper needed"
    @Published private(set) var progress=0
    @Published private(set) var targetCounts=[0,0,0]
    @Published private(set) var lowCount=0
    @Published var helperPresent=false
    @Published private(set) var polygons=[[SIMD2<Float>]]()
    @Published private(set) var exclusions=[[Float]]()
    @Published private(set) var localDistances:[Double?]=[nil,nil,nil]
    @Published private(set) var depthReasons=[String]()
    var onChange: (() -> Void)?
    var onInvalidate: (() -> Void)?
    let device=UIDevice.current.identifierForVendor?.uuidString ?? "local-device-unavailable"
    private var frame: CalibratedCameraFrame?
    private var frameTime: Double?
    private var lastRecord: Double?
    private var window=StableMountWindow()
    private let file: URL
    private let setupFile: URL
    var geometryProfile: MountProfile? { draft ?? profile }
    var eligible: Bool { fresh && step == .idle && profile?.readyForReuse == true && frame?.problem == nil && frame?.summary != nil }
    var wizard: Bool { step != .idle }
    var profileStatus: String { profile == nil ? "Calibration required" : "Saved mount profile · reused automatically" }
    init() {
        let folder=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask).first!
        file=folder.appendingPathComponent("mount-profile-v2.json")
        setupFile=FileManager.default.urls(for:.documentDirectory,in:.userDomainMask).first!.appendingPathComponent("mount-setup-region-v2.json")
        if let data=try? Data(contentsOf:setupFile),data.count<1024,
           let setup=try? JSONDecoder().decode(MountRegion.self,from:data),setup.valid { region=setup }
        if !UserDefaults.standard.bool(forKey:"mount-profile-invalidated"),
           let data=try? Data(contentsOf:file),let loaded=try? MountProfile.load(data),loaded.camera.device==device {
            profile=loaded;region=loaded.region;message="Saved mount profile loaded; waiting for fresh pose, floor and depth"
        }
    }
    private func persistRegion() {
        if let data=try? JSONEncoder().encode(region) { try? data.write(to:setupFile,options:[.atomic,.completeFileProtection]) }
    }
    private func invalidateStored() {
        UserDefaults.standard.set(true,forKey:"mount-profile-invalidated")
        profile=nil;draft=nil
        try? FileManager.default.removeItem(at:file)
    }
    func begin() {
        onInvalidate?()
        invalidateStored();persistRegion();step = .position;helperPresent=false;targetCounts=[0,0,0];lowCount=0
        resetTransient();message="Helper: position the full-width yellow band at normal cane grip/angle"
        onChange?()
    }
    func moved() { begin();message="Mount changed or uncertain · old profile invalidated; helper must recalibrate" }
    func moveRegion(y: Float) {
        guard step == .position else { return }
        region=MountRegion(y:y-region.height/2,height:region.height)
        persistRegion();resetTransient();onChange?()
    }
    func resizeRegion(height: Float) {
        guard step == .position else { return }
        let centre=region.y+region.height/2
        region=MountRegion(y:centre-height/2,height:height)
        persistRegion();resetTransient();onChange?()
    }
    func collect() {
        guard step == .position,helperPresent,let frame,frame.problem == nil,
              let candidate=frame.candidate,fresh else { message="Need helper confirmation, fresh depth and level floor first";return }
        draft=candidate;step = .stable;window.reset();progress=0
        message="Hold still for a short neutral capture";onChange?()
    }
    private var fresh: Bool { frameTime.map { CACurrentMediaTime()-$0>=0 && CACurrentMediaTime()-$0<0.5 } ?? false }
    func observe(_ value: CalibratedCameraFrame,timestamp: Double) {
        frame=value;frameTime=timestamp;polygons=value.polygons;exclusions=value.exclusions
        localDistances=value.summary?.sectors.map(\.distanceMetres) ?? [nil,nil,nil]
        let qualities=value.diagnostics["sector_input_quality"] as? [[String:Int]] ?? []
        depthReasons=(value.summary?.sectors.enumerated().map { index,sector in
            let name=["Left","Center","Right"][index],coverage=Int((sector.validFraction ?? 0)*100)
            let quality=index<qualities.count ? qualities[index] : [:]
            if sector.evidence == .measured { return "\(name): measured · \(coverage)% usable" }
            if (quality["sector_not_visible"] ?? 0)>0 { return "\(name): partly outside camera view" }
            let far=quality["over_2m_raw"] ?? 0,farHigh=quality["over_2m_high"] ?? 0
            if far>0 && farHigh==0 { return "\(name): far depth present, but confidence too low" }
            if (quality["floor_excluded"] ?? 0)>0 { return "\(name): floor removed; \(coverage)% usable (need 25%)" }
            if (quality["outside_range"] ?? 0)>0 { return "\(name): samples outside 0.25–4 m range; \(coverage)% usable" }
            return "\(name): \(coverage)% usable high-confidence depth (need 25% and 32 samples)"
        }) ?? []
        // A temporary camera configuration mismatch cannot establish a slipped
        // mount. Retain the confirmed profile; unsupported frames stay gated.
        if value.incompatible,profile != nil {
            message="Camera configuration unavailable; saved calibration retained"
            window.reset();progress=0;return
        }
        if let problem=value.problem { message=problem;window.reset();progress=0;return }
        if step == .stable,let pose=value.pose,let height=value.height {
            if let draft {
                let r=simd_transpose(draft.neutral)*pose
                let cosine=max(-1,min(1,(r.columns.0.x+r.columns.1.y+r.columns.2.z-1)/2))
                if acos(cosine)>2 * .pi/180 || abs(height-draft.cameraHeight)>0.03 {
                    window.reset();progress=0
                    message="Neutral mount moved; return to captured angle or start Calibrate mount again";return
                }
            }
            let good=(value.summary?.sectors.contains { $0.evidence == .measured } == true) &&
                (value.summary?.sectors.reduce(0) { $0+$1.validSamples } ?? 0)>=96
            if window.observe(timestamp:timestamp,now:CACurrentMediaTime(),pose:pose,height:height,usable:good) {
                step = .left;message="Helper: place broad target in yellow LEFT third; record three fresh samples"
            }
            progress=window.count
        } else if step == .idle {
            message=profile == nil ? "Calibration required · sighted helper needed" : "Calibrated region active · obstacle sides, no movement recommendation"
        }
    }
    func recordTarget() {
        guard helperPresent,fresh,let frame,frame.problem == nil,let time=frameTime,
              lastRecord.map({ time-$0>=0.3 }) ?? true else { message="Wait for a fresh supported frame";return }
        if step == .low {
            guard frame.lowPixels>=32,frame.summary?.sectors.contains(where: { $0.evidence == .measured }) == true else {
                message="Need a known 8–20 cm high obstacle measured inside the yellow region; do not use floor";return
            }
            lowCount+=1;lastRecord=time
            if lowCount>=3 { step = .confirm;message="Helper: verify mount unchanged and save completed calibration" }
            return
        }
        let target: Int
        switch step { case .left:target=0;case .center:target=1;case .right:target=2;default:return }
        guard let sectors=frame.summary?.sectors,sectors.count==3,
              sectors[target].evidence == .measured,sectors[target].distanceMetres != nil else {
            message="Requested target is not measured. Check selected-region depth reasons; unknown backgrounds stay unknown.";return
        }
        let known=sectors.map { $0.evidence == .measured ? $0.distanceMetres : nil }
        guard MountTargetEvidence.canRecord(target:target,distances:known) else {
            message="Known target must be at least 15 cm nearer than other measured thirds; adjust target, not thresholds";return
        }
        // The helper identifies the placed target. Unknown background is never
        // interpreted as far/clear and contributes no side-acceptance measurement.
        targetCounts[target]+=1;lastRecord=time
        if targetCounts[target]>=3 {
            step = target==0 ? .center : target==1 ? .right : .low
            message=step == .low ? "Helper: test a known 8–20 cm high obstacle in the region, three fresh samples" : "Helper: place target in yellow \(step.rawValue.uppercased()) third; record three fresh samples"
        }
    }
    func save() {
        guard step == .confirm,helperPresent,targetCounts==[3,3,3],lowCount>=3,fresh,
              frame?.problem == nil,var confirmed=draft else { return }
        confirmed.helperConfirmed=true;confirmed.verifiedSides=[true,true,true];confirmed.lowObstacleVerified=true
        confirmed.confirmedAt=Date()
        do {
            try FileManager.default.createDirectory(at:file.deletingLastPathComponent(),withIntermediateDirectories:true)
            try confirmed.data().write(to:file,options:[.atomic,.completeFileProtection])
            UserDefaults.standard.set(false,forKey:"mount-profile-invalidated")
            profile=confirmed;draft=nil;step = .idle;resetTransient()
            message="Calibration saved; waiting for fresh observations";onChange?()
        } catch { message="Could not save calibration; streaming remains gated" }
    }
    func resetTransient() {
        frame=nil;frameTime=nil;lastRecord=nil;window.reset();progress=0
        polygons=[];exclusions=[];localDistances=[nil,nil,nil];depthReasons=[]
    }
    func trackingReset() {
        resetTransient()
        if wizard { draft=nil;step = .position;targetCounts=[0,0,0];lowCount=0;message="Tracking reset; repeat neutral capture and checks" }
        else { message=profile == nil ? "Calibration required; waiting for fresh tracking" : "Saved mount profile retained; waiting for fresh tracking" }
    }
    var diagnostic: [String:Any] {
        ["profile_loaded":profile?.readyForReuse == true,"wizard_step":step.rawValue,
         "eligible_locally":eligible,"status":message,"stable_frames":progress,
         "side_counts":targetCounts,"low_count":lowCount,"region":[region.x,region.y,MountRegion.width,region.height]]
    }
}
