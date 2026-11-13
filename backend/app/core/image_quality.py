import cv2
import numpy as np
from PIL import Image
import io
from typing import Tuple, List
from ..models.schemas import ImageQualityAssessment
from ..config import settings

def assess_image_quality(image_bytes: bytes) -> ImageQualityAssessment:
    """
    Evaluates blurriness, illumination (dark/glare), resolution, and potential cropping.
    Uses OpenCV and Pillow.
    """
    recommendations: List[str] = []

    # Read with Pillow first to verify integrity and dimensions
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        width, height = pil_img.size
    except Exception as e:
        return ImageQualityAssessment(
            is_acceptable=False,
            blur_score=0.0,
            is_blurry=True,
            brightness_score=0.0,
            is_dark=True,
            is_glare=False,
            aspect_ratio=0.0,
            is_cropped_suspected=True,
            width=0,
            height=0,
            recommendations=["Uploaded file is not a readable or valid image format."]
        )

    # Resolution check
    if width < settings.MIN_IMAGE_WIDTH or height < settings.MIN_IMAGE_HEIGHT:
        recommendations.append(
            f"Image resolution ({width}x{height}) is too low. Please upload a clear photo of at least 800x500 pixels."
        )

    # Convert to OpenCV format (BGR & Gray)
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        return ImageQualityAssessment(
            is_acceptable=False,
            blur_score=0.0,
            is_blurry=True,
            brightness_score=0.0,
            is_dark=True,
            is_glare=False,
            aspect_ratio=0.0,
            is_cropped_suspected=True,
            width=0,
            height=0,
            recommendations=["Image decoding failed. Please upload a standard JPEG or PNG."]
        )

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 1. Blur Detection using Laplacian Variance
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    is_blurry = laplacian_var < settings.BLUR_LAPLACIAN_THRESHOLD
    if is_blurry:
        recommendations.append(
            "The image appears blurry or out-of-focus. Please hold your camera steady, tap to focus on text, and retake the photo."
        )

    # 2. Illumination & Glare Detection
    mean_brightness = float(np.mean(gray))
    is_dark = mean_brightness < settings.DARKNESS_THRESHOLD_MEAN
    if is_dark:
        recommendations.append(
            "The image is too dark or shadowed. Please take the photo in even, well-lit ambient lighting."
        )

    # Glare / Overexposure: ratio of pixels with value >= 245
    glare_pixels = np.sum(gray >= 245)
    total_pixels = gray.size
    glare_ratio = float(glare_pixels) / float(total_pixels)
    is_glare = glare_ratio > settings.GLARE_THRESHOLD_PERCENT
    if is_glare:
        recommendations.append(
            "Flash or bright light reflection (glare) was detected on the card surface. Turn off flash and angle the camera slightly to eliminate reflections."
        )

    # 3. Aspect Ratio and Cropping check
    aspect_ratio = float(width) / float(height) if height > 0 else 0.0
    # Normalize aspect ratio (if user uploaded portrait orientation instead of landscape)
    normalized_ar = aspect_ratio if aspect_ratio >= 1.0 else (1.0 / aspect_ratio if aspect_ratio > 0 else 0)

    # Standard ID card ratio is ~1.586
    # If the image is square (~1.0) or extreme panorama (>2.5), borders may be tightly cut or background excessive
    is_cropped_suspected = False
    if normalized_ar < 1.1 or normalized_ar > 2.6:
        is_cropped_suspected = True
        recommendations.append(
            "The card framing appears unusual or cropped. Ensure the full rectangular card with all four corners is clearly visible."
        )

    is_acceptable = not (is_blurry or is_dark or (width < settings.MIN_IMAGE_WIDTH))

    return ImageQualityAssessment(
        is_acceptable=is_acceptable,
        blur_score=round(laplacian_var, 2),
        is_blurry=is_blurry,
        brightness_score=round(mean_brightness, 2),
        is_dark=is_dark,
        is_glare=is_glare,
        aspect_ratio=round(aspect_ratio, 3),
        is_cropped_suspected=is_cropped_suspected,
        width=width,
        height=height,
        recommendations=recommendations
    )
