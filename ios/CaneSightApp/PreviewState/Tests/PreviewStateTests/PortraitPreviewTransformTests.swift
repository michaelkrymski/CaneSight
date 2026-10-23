#if canImport(CoreImage) && canImport(CoreVideo)
import XCTest
import CoreImage
import CoreVideo
import CaneSightPreviewState

final class PortraitPreviewTransformTests: XCTestCase {
    // CV buffer is in top-left raster order. Red values uniquely identify samples.
    func image(width: Int, height: Int) throws -> CIImage {
        var value: CVPixelBuffer?
        XCTAssertEqual(CVPixelBufferCreate(kCFAllocatorDefault,width,height,kCVPixelFormatType_32BGRA,nil,&value), kCVReturnSuccess)
        let buffer = try XCTUnwrap(value)
        CVPixelBufferLockBaseAddress(buffer,[])
        let bytes = CVPixelBufferGetBaseAddress(buffer)!.assumingMemoryBound(to: UInt8.self)
        let stride = CVPixelBufferGetBytesPerRow(buffer)
        for y in 0..<height { for x in 0..<width {
            let o = y*stride+x*4; bytes[o]=0; bytes[o+1]=0
            bytes[o+2]=UInt8((y*width+x+1)*10); bytes[o+3]=255
        } }
        CVPixelBufferUnlockBaseAddress(buffer,[])
        return CIImage(cvPixelBuffer:buffer).samplingNearest()
    }
    func rendered(_ transform: CGAffineTransform, outputWidth: Int, outputHeight: Int) throws -> [Int] {
        let source = try image(width:6,height:3)
        let pixels = try PortraitPreviewTransform.pixels(imageWidth:6,imageHeight:3,
            previewWidth:Double(outputWidth),previewHeight:Double(outputHeight),normalized:transform)
        let context = CIContext(options:[.useSoftwareRenderer:false])
        let cg = try XCTUnwrap(context.createCGImage(source.transformed(by:pixels),
            from:CGRect(x:0,y:0,width:outputWidth,height:outputHeight),format:.RGBA8,colorSpace:CGColorSpaceCreateDeviceRGB()))
        let bytes = try XCTUnwrap(cg.dataProvider?.data) as Data
        return (0..<outputHeight).flatMap { y in (0..<outputWidth).map { x in Int((Double(bytes[y*cg.bytesPerRow+x*4])/10).rounded()) } }
    }
    func testRenderedPreviewQuarterTurnsMatchIndependentTopLeftMarkerOracles() throws {
        XCTAssertEqual(try rendered(CGAffineTransform(a:0,b:-1,c:1,d:0,tx:0,ty:1),outputWidth:3,outputHeight:6),
            [6,12,18,5,11,17,4,10,16,3,9,15,2,8,14,1,7,13])
        XCTAssertEqual(try rendered(CGAffineTransform(a:0,b:1,c:-1,d:0,tx:1,ty:0),outputWidth:3,outputHeight:6),
            [13,7,1,14,8,2,15,9,3,16,10,4,17,11,5,18,12,6])
    }
    func testRenderedIdentityAndHalfTurnPreserveTheExpectedRows() throws {
        XCTAssertEqual(try rendered(.identity,outputWidth:6,outputHeight:3),Array(1...18))
        XCTAssertEqual(try rendered(CGAffineTransform(a:-1,b:0,c:0,d:-1,tx:1,ty:1),outputWidth:6,outputHeight:3),Array((1...18).reversed()))
    }
    func testAspectFillClipsMarkersOutsideTheVisibleViewport() throws {
        // Exactly doubled X scale crops source columns 1 and 6. No target is
        // silently pulled from outside the same visible region used for depth.
        let values = try rendered(CGAffineTransform(a:1.5,b:0,c:0,d:1,tx:-0.25,ty:0),outputWidth:4,outputHeight:3)
        XCTAssertEqual(values,[2,3,4,5,8,9,10,11,14,15,16,17])
    }
}
#endif
