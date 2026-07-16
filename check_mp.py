import mediapipe
print("version:", mediapipe.__version__)
try:
    from mediapipe.tasks import python as mp_tasks
    print("tasks available:", dir(mp_tasks))
    from mediapipe.tasks.python import vision
    print("vision:", dir(vision))
    print("ObjectDetector:", hasattr(vision, 'ObjectDetector'))
except Exception as e:
    print("tasks error:", e)
