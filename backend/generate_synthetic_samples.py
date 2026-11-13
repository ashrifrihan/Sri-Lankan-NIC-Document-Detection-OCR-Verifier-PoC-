import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

def get_font(size: int):
    try:
        # Standard Windows fonts
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()

def get_bold_font(size: int):
    try:
        return ImageFont.truetype("arialbd.ttf", size)
    except Exception:
        return get_font(size)

def create_synthetic_samples(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    w, h = 856, 540  # Standard ID-1 aspect ratio at 10x scale

    font_title = get_bold_font(24)
    font_sub = get_font(18)
    font_body = get_font(20)
    font_num = get_bold_font(26)

    # 1. Synthetic Old Laminated Card (Blue-violet, 9-digit format)
    old_card = Image.new("RGB", (w, h), color=(170, 190, 225))
    draw = ImageDraw.Draw(old_card)
    # Draw fine guilloche-like grid
    for x in range(0, w, 20):
        draw.line([(x, 0), (x + 30, h)], fill=(155, 175, 215), width=1)
    for y in range(0, h, 20):
        draw.line([(0, y), (w, y + 20)], fill=(155, 175, 215), width=1)
    # Lamination border
    draw.rectangle([15, 15, w - 15, h - 15], outline=(120, 140, 180), width=4)
    # Header
    draw.text((100, 35), "DEMOCRATIC SOCIALIST REPUBLIC OF SRI LANKA", fill=(20, 30, 80), font=font_title)
    draw.text((260, 70), "NATIONAL IDENTITY CARD", fill=(20, 30, 80), font=font_sub)
    # Photo box
    draw.rectangle([50, 120, 250, 380], fill=(210, 220, 235), outline=(60, 70, 100), width=2)
    draw.text((90, 240), "[ PHOTO ]", fill=(80, 90, 110), font=font_sub)
    # Details
    draw.text((300, 150), "IDENTITY NO:", fill=(40, 40, 60), font=font_sub)
    draw.text((450, 148), "853451234V", fill=(10, 10, 30), font=font_num)
    draw.text((300, 210), "FULL NAME:", fill=(40, 40, 60), font=font_sub)
    draw.text((450, 210), "K. A. PERERA", fill=(10, 10, 30), font=font_body)
    draw.text((300, 270), "DATE OF BIRTH:", fill=(40, 40, 60), font=font_sub)
    draw.text((450, 270), "1985-12-11", fill=(10, 10, 30), font=font_body)
    draw.text((300, 330), "PLACE OF ISSUE:", fill=(40, 40, 60), font=font_sub)
    draw.text((450, 330), "COLOMBO", fill=(10, 10, 30), font=font_body)
    old_card.save(os.path.join(output_dir, "synthetic_old_laminated.png"))

    # 2. Synthetic Printed Laminated Card (Cyan background, dot-matrix/printed feel)
    printed_card = Image.new("RGB", (w, h), color=(195, 230, 240))
    draw_p = ImageDraw.Draw(printed_card)
    # Printed border
    draw_p.rectangle([20, 20, w - 20, h - 20], outline=(100, 160, 190), width=3)
    draw_p.text((120, 40), "SRI LANKA IDENTITY CARD", fill=(10, 50, 70), font=font_title)
    draw_p.rectangle([60, 130, 240, 370], fill=(225, 245, 250), outline=(100, 160, 190), width=2)
    draw_p.text((90, 240), "[ PHOTO ]", fill=(80, 120, 140), font=font_sub)
    draw_p.text((290, 150), "NIC NO:", fill=(20, 60, 80), font=font_sub)
    draw_p.text((420, 146), "927891234X", fill=(10, 30, 50), font=font_num)
    draw_p.text((290, 210), "NAME:", fill=(20, 60, 80), font=font_sub)
    draw_p.text((420, 210), "M. S. FERNANDO", fill=(10, 30, 50), font=font_body)
    draw_p.text((290, 270), "DOB:", fill=(20, 60, 80), font=font_sub)
    draw_p.text((420, 270), "1992-10-15", fill=(10, 30, 50), font=font_body)
    printed_card.save(os.path.join(output_dir, "synthetic_printed_laminated.png"))

    # 3. Synthetic Smart Card (Polycarbonate with Chip, 12-digit format)
    smart_card = Image.new("RGB", (w, h), color=(248, 250, 252))
    draw_s = ImageDraw.Draw(smart_card)
    # Security header band
    draw_s.rectangle([0, 0, w, 80], fill=(220, 235, 250))
    draw_s.text((80, 15), "SRI LANKA  |  ශ්‍රී ලංකා  |  இலங்கை", fill=(20, 40, 70), font=font_title)
    draw_s.text((80, 48), "NATIONAL IDENTITY CARD", fill=(60, 80, 110), font=font_sub)
    # Smart Chip representation (gold metallic rectangle with contact pads)
    draw_s.rectangle([90, 180, 210, 290], fill=(218, 165, 32), outline=(184, 134, 11), width=3)
    draw_s.line([(150, 180), (150, 290)], fill=(184, 134, 11), width=2)
    draw_s.line([(90, 235), (210, 235)], fill=(184, 134, 11), width=2)
    # Photo
    draw_s.rectangle([620, 120, 800, 360], fill=(235, 240, 248), outline=(160, 180, 210), width=2)
    draw_s.text((660, 230), "[ PHOTO ]", fill=(100, 120, 150), font=font_sub)
    # Text details
    draw_s.text((260, 130), "NIC NUMBER:", fill=(50, 60, 80), font=font_sub)
    draw_s.text((260, 160), "199518001234", fill=(10, 20, 40), font=font_num)
    draw_s.text((260, 220), "FULL NAME:", fill=(50, 60, 80), font=font_sub)
    draw_s.text((260, 250), "NIMAL SILVA", fill=(10, 20, 40), font=font_body)
    draw_s.text((260, 310), "DATE OF BIRTH:", fill=(50, 60, 80), font=font_sub)
    draw_s.text((260, 340), "1995-06-29", fill=(10, 20, 40), font=font_body)
    smart_card.save(os.path.join(output_dir, "synthetic_smart_card.png"))

    # 4. Blurry Card (Gaussian Blur)
    blurry_card = smart_card.filter(ImageFilter.GaussianBlur(radius=8))
    blurry_card.save(os.path.join(output_dir, "synthetic_blurry.png"))

    # 5. Dark/Underexposed Card
    arr = np.array(smart_card, dtype=np.float32)
    arr = (arr * 0.12).astype(np.uint8)  # severe underexposure
    dark_card = Image.fromarray(arr)
    dark_card.save(os.path.join(output_dir, "synthetic_dark.png"))

    # 6. Random Non-NIC Image (Noise & abstract geometric shapes)
    non_nic = Image.new("RGB", (w, h), color=(255, 230, 200))
    draw_nn = ImageDraw.Draw(non_nic)
    for i in range(15):
        draw_nn.ellipse([i*50, i*30, i*50+120, i*30+120], outline=(200, 50, 50), width=3)
    draw_nn.text((200, 250), "RECEIPT INVOICE #99812", fill=(50, 50, 50), font=font_title)
    draw_nn.text((200, 300), "Grocery Store Supermarket", fill=(80, 80, 80), font=font_sub)
    non_nic.save(os.path.join(output_dir, "synthetic_not_nic.png"))

    print(f"Synthetic test samples generated successfully in '{output_dir}'.")

if __name__ == "__main__":
    create_synthetic_samples("samples")
