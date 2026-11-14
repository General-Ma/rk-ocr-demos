import base64
import numpy as np
import pymupdf
from .ground_truth import parse_csv
from .ocr import make_engine, extract_page
from .compare import compare

MAX_PAGES = 12


def process(pdf_bytes, csv_bytes):
    truth = parse_csv(csv_bytes)
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype='pdf')
    except Exception as exc:
        raise ValueError('The PDF is unreadable or damaged.') from exc
    with document:
        if document.needs_pass:
            raise ValueError('Password-protected PDFs are not supported.')
        if not 1 <= len(document) <= MAX_PAGES:
            raise ValueError(f'PDF must contain 1–{MAX_PAGES} pages.')
        engine = make_engine()
        readings, pages = [], []
        for number, page in enumerate(document, start=1):
            if page.rect.width <= 0 or page.rect.height <= 0:
                raise ValueError('The PDF contains an invalid page size.')
            scale = 2000 / max(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale,scale), colorspace=pymupdf.csRGB, alpha=False)
            pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height,pix.width,3)
            readings.extend(extract_page(engine, pixels[:,:,::-1].copy(), number))
            pages.append({'page':number, 'image':'data:image/jpeg;base64,'+base64.b64encode(pix.tobytes('jpeg',jpg_quality=80)).decode('ascii')})
        if not readings:
            raise ValueError('No supported vital-sign forms were detected. Use an upright, legible scan of the demonstrated chart layout.')
        return {**compare(readings,truth), 'pages':pages}


def worker(connection, pdf_bytes, csv_bytes):
    try:
        connection.send(('ok', process(pdf_bytes,csv_bytes)))
    except ValueError as exc:
        connection.send(('validation', str(exc)))
    except Exception:
        # Do not return OCR-library exceptions: they may contain document text.
        connection.send(('error','OCR processing failed. Check the local model installation and try a smaller, upright scan.'))
    finally:
        connection.close()
