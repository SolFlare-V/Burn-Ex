from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision
import inspect

# Check ObjectDetectorOptions and BaseOptions
print("BaseOptions sig:", inspect.signature(mp_tasks.BaseOptions.__init__))
print("ObjectDetectorOptions sig:", inspect.signature(vision.ObjectDetectorOptions.__init__))
print("ObjectDetector.create_from_options sig:", inspect.signature(vision.ObjectDetector.create_from_options))

# Check detection result structure
import mediapipe as mp
print("\nDetection classes:")
from mediapipe.tasks.python.components.containers import detections
print(dir(detections))
