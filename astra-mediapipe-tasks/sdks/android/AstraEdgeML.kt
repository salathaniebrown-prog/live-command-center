package com.astra.edgeml
import android.content.Context
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector
import com.google.mediapipe.tasks.text.textclassifier.TextClassifier
import com.google.mediapipe.tasks.text.textembedder.TextEmbedder
import com.google.mediapipe.tasks.audio.audioclassifier.AudioClassifier

class AstraEdgeML(private val ctx: Context) {
    private fun gpuOpts(asset: String) = BaseOptions.builder().setModelAssetPath(asset).setDelegate(Delegate.GPU).build()
    val vision = ObjectDetector.createFromOptions(ctx, ObjectDetector.ObjectDetectorOptions.builder().setBaseOptions(gpuOpts("efficientdet_lite0.tflite")).build())
    val text = TextClassifier.createFromOptions(ctx, TextClassifier.TextClassifierOptions.builder().setBaseOptions(gpuOpts("bert_classifier.tflite")).build())
    val retrieval = TextEmbedder.createFromOptions(ctx, TextEmbedder.TextEmbedderOptions.builder().setBaseOptions(gpuOpts("universal_sentence_encoder.tflite")).build())
    val audio = AudioClassifier.createFromOptions(ctx, AudioClassifier.AudioClassifierOptions.builder().setBaseOptions(gpuOpts("yamnet.tflite")).build())
}
