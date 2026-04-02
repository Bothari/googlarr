FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install required system libraries
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgles2 \
    libegl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Download mediapipe model files (before COPY so they're cached separately)
RUN mkdir -p assets && python -c "\
import urllib.request; \
print('Downloading face detector model...'); \
urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite', 'assets/face_detector.tflite'); \
print('Downloading face landmarker model...'); \
urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task', 'assets/face_landmarker.task'); \
print('Models downloaded.') \
"

COPY . .

CMD ["python", "-m", "googlarr.main"]
