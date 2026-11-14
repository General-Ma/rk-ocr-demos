import base64
from contextlib import ExitStack
import numpy as np
import pymupdf
from .ground_truth import parse_csv
from .ocr import make_engine, extract_page
from .compare import compare

MAX_PAGES = 12


def extract_documents(uploads, progress=None):
    """Extract ordered PDFs without consulting a main source or comparing values."""
    def notify(phase, **details):
        if progress:
            progress({'phase':phase, **details})

    notify('validating')
    with ExitStack() as stack:
        documents = []
        for name, content in uploads:
            try:
                document = stack.enter_context(pymupdf.open(stream=content, filetype='pdf'))
            except Exception as exc:
                raise ValueError('A PDF is unreadable or damaged.') from exc
            if document.needs_pass:
                raise ValueError('Password-protected PDFs are not supported.')
            if len(document) == 0:
                raise ValueError('Each PDF must contain at least one page.')
            documents.append((name, document))
        total_pages = sum(len(doc) for _, doc in documents)
        if not 1 <= total_pages <= MAX_PAGES:
            raise ValueError(f'Upload 1–{MAX_PAGES} pages in total across all PDFs.')
        notify('loading')
        engine = make_engine()
        extracted, pages = [], []
        for document_index, (name, document) in enumerate(documents):
            readings = []
            for local_page, page in enumerate(document, start=1):
                if page.rect.width <= 0 or page.rect.height <= 0:
                    raise ValueError('The PDF contains an invalid page size.')
                notify('rendering', page=len(pages)+1, completed_pages=len(pages), total_pages=total_pages)
                scale = 2000 / max(page.rect.width, page.rect.height)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(scale,scale), colorspace=pymupdf.csRGB, alpha=False)
                pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height,pix.width,3)
                global_page = len(pages) + 1
                notify('reading', page=global_page, completed_pages=len(pages), total_pages=total_pages)
                found = extract_page(engine, pixels[:,:,::-1].copy(), global_page)
                for reading in found:
                    reading.update(document_index=document_index, document_name=name, local_page=local_page)
                readings.extend(found)
                pages.append({'page':global_page, 'document_name':name, 'local_page':local_page,
                              'image':'data:image/jpeg;base64,'+base64.b64encode(pix.tobytes('jpeg',jpg_quality=80)).decode('ascii')})
                notify('reading', page=global_page, completed_pages=len(pages), total_pages=total_pages)
            extracted.append({'name':name, 'readings':readings})
        if not any(doc['readings'] for doc in extracted):
            raise ValueError('No supported vital-sign forms were detected. Use an upright, legible scan of the demonstrated chart layout.')
        notify('preparing')
        return {'documents':extracted, 'pages':pages}


def audit_documents(documents, truth):
    readings = [reading for doc in documents for reading in doc['readings']]
    report = compare(readings, truth)
    report['documents'] = [{'name':'Combined documents', 'aligned':report['aligned'], 'note':report['alignment_note']}]
    return report


def process(pdf_bytes, csv_bytes):
    # Retain the original endpoint for existing clients.
    truth = parse_csv(csv_bytes)
    extraction = extract_documents([('Document.pdf', pdf_bytes)])
    return {**audit_documents(extraction['documents'], truth), 'pages':extraction['pages']}


def send_result(connection, operation, *args):
    try:
        connection.send(('ok', operation(*args)))
    except ValueError as exc:
        connection.send(('validation', str(exc)))
    except Exception:
        connection.send(('error','OCR processing failed. Check the local model installation and try a smaller, upright scan.'))
    finally:
        connection.close()


def worker(connection, pdf_bytes, csv_bytes):
    send_result(connection, process, pdf_bytes, csv_bytes)


def extraction_worker(connection, uploads):
    send_result(connection, extract_documents, uploads, lambda update: connection.send(('progress', update)))
