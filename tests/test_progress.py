import json
import pymupdf
from fastapi.testclient import TestClient
from app.main import app
from app.services.pipeline import extract_documents

client = TestClient(app)
HEADERS = {'accept':'application/x-ndjson'}


def events(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_page_progress_tracks_completed_work(monkeypatch):
    with pymupdf.open() as doc:
        doc.new_page()
        pdf = doc.tobytes()
    updates = []
    monkeypatch.setattr('app.services.pipeline.make_engine',lambda: object())
    def recognize(engine, image, page):
        assert updates[-1] == {'phase':'reading','page':page,'completed_pages':page-1,'total_pages':2}
        return [{'page':page}]
    monkeypatch.setattr('app.services.pipeline.extract_page',recognize)
    extract_documents([('a.pdf',pdf),('b.pdf',pdf)], updates.append)
    assert [item['phase'] for item in updates] == [
        'validating','loading','rendering','reading','reading','rendering','reading','reading','preparing']
    assert updates[-2]['completed_pages'] == 2
    assert all(set(item) <= {'phase','page','completed_pages','total_pages'} for item in updates)


def test_stream_delivers_progress_then_result_and_releases_lock(monkeypatch):
    async def worker(*args, **kwargs):
        assert client.get('/api/health').json()['processing']
        yield 'progress', {'phase':'loading'}
        yield 'heartbeat', {}
        yield 'progress', {'phase':'reading','page':1,'completed_pages':0,'total_pages':1}
        yield 'ok', {'documents':[], 'pages':[]}
    monkeypatch.setattr('app.main.worker_events',worker)
    response = client.post('/api/extract',headers=HEADERS,files={'pdfs':('scan.pdf',b'%PDF- test')})
    assert response.headers['content-type'].startswith('application/x-ndjson')
    assert response.headers['cache-control'] == 'no-store'
    assert [item['type'] for item in events(response)] == ['progress','progress','result']
    assert not client.get('/api/health').json()['processing']


def test_nonstream_client_still_gets_json(monkeypatch):
    async def worker(*args, **kwargs):
        yield 'progress', {'phase':'reading'}
        yield 'ok', {'documents':[], 'pages':[]}
    monkeypatch.setattr('app.main.worker_events',worker)
    response = client.post('/api/extract',files={'pdfs':('scan.pdf',b'%PDF- test')})
    assert response.json() == {'documents':[], 'pages':[]}


def test_streamed_worker_validation_error():
    response = client.post('/api/extract',headers=HEADERS,files={'pdfs':('scan.pdf',b'%PDF- broken')})
    result = events(response)
    assert result[0] == {'type':'progress','phase':'validating'}
    assert result[-1]['type'] == 'error'
    assert 'unreadable' in result[-1]['detail']
    assert not client.get('/api/health').json()['processing']


def test_streamed_timeout_releases_lock(monkeypatch):
    monkeypatch.setattr('app.main.TIMEOUT_SECONDS',-1)
    response = client.post('/api/extract',headers=HEADERS,files={'pdfs':('scan.pdf',b'%PDF- test')})
    result = events(response)
    assert result[-1]['type'] == 'error'
    assert '10-minute' in result[-1]['detail']
    assert not client.get('/api/health').json()['processing']
