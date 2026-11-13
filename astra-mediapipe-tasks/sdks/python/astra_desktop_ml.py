import os, sys
from mediapipe.tasks import python
from mediapipe.tasks.python import vision, text, audio

MODELS = os.path.expanduser("~/astra-mediapipe-tasks/models")
def base_opts(name, use_gpu=True):
    delegate = python.BaseOptions.Delegate.GPU if use_gpu else python.BaseOptions.Delegate.CPU
    return python.BaseOptions(model_asset_path=os.path.join(MODELS, name), delegate=delegate)

def load_desktop_pipeline(use_gpu=True):
    return {
        "vision": vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(base_options=base_opts("efficientdet_lite0.tflite", use_gpu))),
        "text": text.TextClassifier.create_from_options(text.TextClassifierOptions(base_options=base_opts("bert_classifier.tflite", use_gpu))),
        "retrieval": text.TextEmbedder.create_from_options(text.TextEmbedderOptions(base_options=base_opts("universal_sentence_encoder.tflite", use_gpu))),
        "audio": audio.AudioClassifier.create_from_options(audio.AudioClassifierOptions(base_options=base_opts("yamnet.tflite", use_gpu))),
    }

if __name__ == "__main__":
    print("Desktop MediaPipe Pipeline Ready on:", sys.platform)
