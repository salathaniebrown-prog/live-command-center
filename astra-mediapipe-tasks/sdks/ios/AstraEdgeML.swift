import Foundation
import MediaPipeTasksVision
import MediaPipeTasksText
import MediaPipeTasksAudio

final class AstraEdgeML {
    func buildVision() throws -> ObjectDetector {
        let opts = ObjectDetectorOptions()
        opts.baseOptions.modelAssetPath = Bundle.main.path(forResource: "efficientdet_lite0", ofType: "tflite") ?? ""
        opts.baseOptions.delegate = .GPU
        return try ObjectDetector(options: opts)
    }
    func buildText() throws -> TextClassifier {
        let opts = TextClassifierOptions()
        opts.baseOptions.modelAssetPath = Bundle.main.path(forResource: "bert_classifier", ofType: "tflite") ?? ""
        opts.baseOptions.delegate = .GPU
        return try TextClassifier(options: opts)
    }
    func buildAudio() throws -> AudioClassifier {
        let opts = AudioClassifierOptions()
        opts.baseOptions.modelAssetPath = Bundle.main.path(forResource: "yamnet", ofType: "tflite") ?? ""
        opts.baseOptions.delegate = .GPU
        return try AudioClassifier(options: opts)
    }
}
