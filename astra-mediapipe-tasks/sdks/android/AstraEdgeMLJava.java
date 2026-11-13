package com.astra.edgeml;
import android.content.Context;
import com.google.mediapipe.tasks.core.BaseOptions;
import com.google.mediapipe.tasks.core.Delegate;
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector;
import com.google.mediapipe.tasks.text.textclassifier.TextClassifier;
import com.google.mediapipe.tasks.audio.audioclassifier.AudioClassifier;

public class AstraEdgeMLJava {
    private static BaseOptions gpuOpts(String asset) {
        return BaseOptions.builder().setModelAssetPath(asset).setDelegate(Delegate.GPU).build();
    }
    public static ObjectDetector createVision(Context ctx) {
        return ObjectDetector.createFromOptions(ctx, ObjectDetector.ObjectDetectorOptions.builder().setBaseOptions(gpuOpts("efficientdet_lite0.tflite")).build());
    }
    public static TextClassifier createText(Context ctx) {
        return TextClassifier.createFromOptions(ctx, TextClassifier.TextClassifierOptions.builder().setBaseOptions(gpuOpts("bert_classifier.tflite")).build());
    }
    public static AudioClassifier createAudio(Context ctx) {
        return AudioClassifier.createFromOptions(ctx, AudioClassifier.AudioClassifierOptions.builder().setBaseOptions(gpuOpts("yamnet.tflite")).build());
    }
}
