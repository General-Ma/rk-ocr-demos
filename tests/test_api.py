from fastapi.testclient import TestClient
from app.main import app, MAX_BODY

client=TestClient(app)


def test_health():
    response=client.get('/api/health')
    assert response.status_code==200
    assert response.headers['cache-control']=='no-store'


def test_missing_files():
    assert client.post('/api/ocr').status_code==422


def test_invalid_pdf():
    response=client.post('/api/ocr',files={'pdf':('scan.pdf',b'not pdf'),'csv':('truth.csv',b'Reading,10:00 AM\nWeight,75')})
    assert response.status_code==422
    assert 'not a PDF' in response.json()['detail']


def test_oversized_stream():
    response=client.post('/api/ocr',content=b'x'*(MAX_BODY+1),headers={'content-type':'multipart/form-data; boundary=test'})
    assert response.status_code==413


def test_malformed_pdf_in_worker():
    response=client.post('/api/ocr',files={'pdf':('scan.pdf',b'%PDF- broken'),'csv':('truth.csv',b'Reading,10:00 AM\nWeight,75')})
    assert response.status_code==422
    assert 'unreadable' in response.json()['detail']


def test_processing_timeout(monkeypatch):
    monkeypatch.setattr('app.main.TIMEOUT_SECONDS', -1)
    response=client.post('/api/ocr',files={'pdf':('scan.pdf',b'%PDF- test'),'csv':('truth.csv',b'Reading,10:00 AM\nWeight,75')})
    assert response.status_code==504
    assert client.get('/api/health').json()['processing'] is False
