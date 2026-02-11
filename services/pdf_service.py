import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter, ImageStat
import io
from typing import List


def pdf_to_images(pdf_bytes: bytes, dpi: int = 300, split: int = 1) -> List[Image.Image]:
    """PDF 바이트를 PIL 이미지 리스트로 변환
    split: 페이지를 세로로 몇 등분할지 (1=분할없음, 2=2등분, 3=3등분)
    """
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes))
        image = preprocess_image(image)

        if split > 1:
            images.extend(_split_image(image, split))
        else:
            images.append(image)

    doc.close()
    return images


def _split_image(image: Image.Image, n: int) -> List[Image.Image]:
    """이미지를 세로로 n등분. 10% 오버랩으로 경계 행 누락 방지"""
    w, h = image.size
    chunk = h // n
    overlap = int(chunk * 0.1)  # 10% 오버랩
    parts = []

    for i in range(n):
        top = max(0, i * chunk - overlap)
        bottom = min(h, (i + 1) * chunk + overlap)
        parts.append(image.crop((0, top, w, bottom)))

    return parts


def preprocess_image(image: Image.Image) -> Image.Image:
    """GPT 인식률 최적화를 위한 이미지 전처리"""
    image = image.convert("RGB")

    # ── 방법 1: 자동 대비 보정 ──────────────────────────────
    # 이미지 밝기 분포 분석 → 어두운 스캔에만 대비 강화
    stat = ImageStat.Stat(image.convert("L"))
    mean_brightness = stat.mean[0]   # 0(검정) ~ 255(흰색)
    stddev = stat.stddev[0]          # 대비 수준 (낮을수록 뿌옇고 흐림)

    # 밝기 낮거나(어두운 스캔) 표준편차 낮으면(뿌연 스캔) 대비 강화
    if mean_brightness < 200 or stddev < 60:
        # 강화 수치를 밝기/대비 상태에 따라 동적으로 계산
        contrast_factor = 1.0 + max(0, (200 - mean_brightness) / 200) * 0.8
        contrast_factor += max(0, (60 - stddev) / 60) * 0.4
        contrast_factor = min(contrast_factor, 2.2)  # 최대 2.2 캡
        image = ImageEnhance.Contrast(image).enhance(contrast_factor)

    # 밝기도 살짝 보정 (너무 어두운 스캔)
    if mean_brightness < 180:
        brightness_factor = 1.0 + (180 - mean_brightness) / 400
        image = ImageEnhance.Brightness(image).enhance(brightness_factor)

    # ── 방법 1: 언샤프 마스크 샤프닝 ────────────────────────
    # 일반 SHARPEN보다 부드럽고 자연스럽게 선명도 향상
    image = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))

    # ── 방법 3: 조건부 리사이즈 ─────────────────────────────
    # GPT-4o 최적 처리 사이즈: 긴 변 2048px 이내
    # 이미 그 이하면 리사이즈 안 함 (작은 글씨 뭉개짐 방지)
    max_side = 2048
    w, h = image.size
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        image = image.resize(new_size, Image.LANCZOS)

    return image


def image_to_bytes(image: Image.Image) -> bytes:
    """PIL 이미지를 PNG 바이트로 변환"""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
