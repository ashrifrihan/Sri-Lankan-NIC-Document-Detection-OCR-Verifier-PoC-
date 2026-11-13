import cv2
import numpy as np


def straighten_card(image: np.ndarray) -> np.ndarray:
    """Perspective-correct a prominent card outline when all four edges are visible."""
    height, width = image.shape[:2]
    scale = min(1.0, 900 / max(height, width))
    preview = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(preview, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 30, 100)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:20]:
        area = cv2.contourArea(contour) / edges.size
        if not .22 <= area <= .96:
            continue
        quad = cv2.approxPolyDP(contour, .025 * cv2.arcLength(contour, True), True)
        if len(quad) != 4 or not cv2.isContourConvex(quad):
            continue
        points = quad.reshape(4, 2).astype(np.float32)
        if (points < 2).any() or (points >= np.array(edges.shape[::-1]) - 2).any():
            continue
        x, y, w, h = cv2.boundingRect(quad)
        if cv2.contourArea(contour) < .72 * w * h:
            continue
        order = np.argsort(points[:, 1])
        top = sorted(points[order[:2]], key=lambda point: point[0])
        bottom = sorted(points[order[2:]], key=lambda point: point[0])
        tl, tr, bl, br = np.array([*top, *bottom]) / scale
        out_w = round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
        out_h = round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
        if min(out_w, out_h) < 40 or not 1.25 <= max(out_w, out_h) / min(out_w, out_h) <= 1.95:
            continue
        target = np.float32([[0, 0], [out_w - 1, 0], [0, out_h - 1], [out_w - 1, out_h - 1]])
        transform = cv2.getPerspectiveTransform(np.float32([tl, tr, bl, br]), target)
        return cv2.warpPerspective(image, transform, (out_w, out_h))
    return image
