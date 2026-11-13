#import <Foundation/Foundation.h>
@import MediaPipeTasksVision;
@import MediaPipeTasksText;
@import MediaPipeTasksAudio;

@interface AstraEdgeMLObjC : NSObject
- (MPPObjectDetector *)createVisionWithError:(NSError **)error;
@end

@implementation AstraEdgeMLObjC
- (MPPObjectDetector *)createVisionWithError:(NSError **)error {
    MPPObjectDetectorOptions *opts = [[MPPObjectDetectorOptions alloc] init];
    opts.baseOptions.modelAssetPath = [[NSBundle mainBundle] pathForResource:@"efficientdet_lite0" ofType:@"tflite"];
    opts.baseOptions.delegate = MPPDelegateGPU;
    return [[MPPObjectDetector alloc] initWithOptions:opts error:error];
}
@end
