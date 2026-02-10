import fitz  # PyMuPDF
from PIL import Image
import io
from typing import List


def pdf_to_images(pdf_bytes: bytes, dpi: int = 300) -> List[Image.Image]:
    """PDF 바이트를 PIL 이미지 리스트로 변환 (DPI 200으로 최적화)"""
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes))
        images.append(image)

    doc.close()
    return images


def image_to_bytes(image: Image.Image) -> bytes:
    """PIL 이미지를 PNG 바이트로 변환"""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
