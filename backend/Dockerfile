# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HOME=/home/verifier HOST=0.0.0.0 PORT=8000 WEB_WORKERS=1 \
    OCR_BACKEND=paddle OCR_WARMUP=true \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libglib2.0-0 libgl1 libtesseract5 \
    tesseract-ocr-eng tesseract-ocr-sin tesseract-ocr-tam \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 verifier

WORKDIR /srv/verifier
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt

COPY app ./app
COPY gunicorn.conf.py .
COPY model-weights ./model-weights
RUN if find model-weights -name '*.pt' -print -quit | grep -q .; then \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-vision.txt; fi

USER verifier
# Download and initialize official Paddle weights during the build.
RUN python -c "from app.core.ocr_backends import PaddleBackend, TesseractBackend; PaddleBackend(); TesseractBackend()"
# Verify both engines initialize and run without outbound access.
RUN --network=none python -c "import cv2, numpy as np; from app.core.ocr_backends import PaddleBackend, TesseractBackend; image = np.full((128, 480, 3), 255, dtype=np.uint8); cv2.putText(image, '199518001234', (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.7, (0, 0, 0), 3); assert all(any('199518001234' in line.text for line in backend.read(image)) for backend in (PaddleBackend(), TesseractBackend()))"

EXPOSE 8000
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app.main:app"]
