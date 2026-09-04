import logging
import io

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract

logger = logging.getLogger(__name__)


def perform_ocr(image_bytes: bytes) -> str:
    """
    Converts uploaded image into plain text using Tesseract OCR.

    Tesseract performs ONLY OCR.
    The returned text is then passed to nlp_service.py,
    which extracts product, quantity and unit.
    """

    try:
        # Load image
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Convert to grayscale
        image = ImageOps.grayscale(image)

        # Increase image size for better character recognition
        width, height = image.size
        image = image.resize(
            (width * 2, height * 2),
            Image.Resampling.LANCZOS
        )

        # Improve contrast
        image = ImageEnhance.Contrast(image).enhance(2.0)

        # Sharpen text
        image = ImageEnhance.Sharpness(image).enhance(2.0)

        # Slight smoothing to reduce noise
        image = image.filter(ImageFilter.MedianFilter(size=3))

        # Tesseract OCR
        text = pytesseract.image_to_string(
            image,
            config="--oem 3 --psm 6"
        )

        text = text.strip()

        logger.info(f"Tesseract extracted text:\n{text}")

        return text

    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        return ""