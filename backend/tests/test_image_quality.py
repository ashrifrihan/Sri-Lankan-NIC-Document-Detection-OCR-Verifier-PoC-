import io
import pytest
from PIL import Image, ImageFilter
import numpy as np
from app.core.image_quality import assess_image_quality

def create_test_image_bytes(is_blurry=False, is_dark=False, size=(800, 500)):
    if is_dark:
        img = Image.new("RGB", size, color=(20, 20, 20))
    else:
        # High contrast image with sharp edges
        img = Image.new("RGB", size, color=(240, 240, 240))
        # Draw some grid lines
        arr = np.array(img)
        arr[::30, :, :] = 0
        arr[:, ::30, :] = 0
        img = Image.fromarray(arr)

    if is_blurry:
        img = img.filter(ImageFilter.GaussianBlur(radius=10))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def test_sharp_image_passes():
    raw = create_test_image_bytes(is_blurry=False, is_dark=False)
    assessment = assess_image_quality(raw)
    assert assessment.is_acceptable is True
    assert assessment.is_blurry is False
    assert assessment.is_dark is False
    assert len(assessment.recommendations) == 0

def test_blurry_image_detected():
    raw = create_test_image_bytes(is_blurry=True, is_dark=False)
    assessment = assess_image_quality(raw)
    assert assessment.is_blurry is True
    assert assessment.is_acceptable is False
    assert any("blurry" in r.lower() for r in assessment.recommendations)

def test_dark_image_detected():
    raw = create_test_image_bytes(is_blurry=False, is_dark=True)
    assessment = assess_image_quality(raw)
    assert assessment.is_dark is True
    assert assessment.is_acceptable is False
    assert any("dark" in r.lower() for r in assessment.recommendations)

def test_corrupt_bytes_handled():
    assessment = assess_image_quality(b"not-an-image-corrupt-data")
    assert assessment.is_acceptable is False
    assert len(assessment.recommendations) > 0
