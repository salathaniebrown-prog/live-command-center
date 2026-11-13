import 'package:mediapipe_vision/mediapipe_vision.dart';
import 'package:mediapipe_text/mediapipe_text.dart';
import 'package:mediapipe_audio/mediapipe_audio.dart';

class AstraEdgeML {
  late ObjectDetector detector;
  late TextClassifier classifier;
  late TextEmbedder embedder;
  late AudioClassifier audio;

  Future<void> initAll() async {
    detector = await ObjectDetector.createFromAsset('assets/efficientdet_lite0.tflite', delegate: HardwareDelegate.gpu);
    classifier = await TextClassifier.createFromAsset('assets/bert_classifier.tflite', delegate: HardwareDelegate.gpu);
    embedder = await TextEmbedder.createFromAsset('assets/universal_sentence_encoder.tflite', delegate: HardwareDelegate.gpu);
    audio = await AudioClassifier.createFromAsset('assets/yamnet.tflite', delegate: HardwareDelegate.gpu);
  }
}
