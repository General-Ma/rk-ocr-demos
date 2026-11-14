import json
import pymupdf
from fastapi.testclient import TestClient
from app.main import app
from app.services.pipeline import extract_documents

client = TestClient(app)


def reading(page=1, minute=605, slot=0):
    return {'page':page, 'local_page':1, 'document_name':'scan.pdf', 'minutes':minute,
            'slot_offset':slot, 'bbox':[.1,.1,.8,.8],
            'fields':{'weight':{'text':'75.4','confidence':.9,'bbox':[.2,.2,.3,.3]}}}


def audit(documents, csv=b'Reading,10:00 AM\nWeight,75.40'):
    return client.post('/api/compare',files={'csv':('truth.csv',csv)},
                       data={'extraction':json.dumps({'documents':documents})})


def test_audit_uses_extraction_without_running_ocr(monkeypatch):
    def unexpected_ocr():
        raise AssertionError('Audit must not run OCR')
    monkeypatch.setattr('app.services.pipeline.make_engine',unexpected_ocr)
    result = audit([{'name':'scan.pdf','readings':[reading()]}])
    assert result.status_code == 200
    assert result.json()['rows'][0]['status'] == 'match'
    assert result.json()['rows'][0]['document_name'] == 'scan.pdf'
    assert 'pages' not in result.json()


def test_duplicate_charts_are_not_audited_independently():
    docs = [{'name':name,'readings':[reading(page=i+1)]} for i,name in enumerate(['first.pdf','second.pdf'])]
    result = audit(docs).json()
    assert not result['aligned']
    assert result['form_count'] == 2
    assert not any(row['status'] == 'match' for row in result['rows'])


def test_split_chart_matches_in_document_order():
    docs = [{'name':'part1.pdf','readings':[reading()]},
            {'name':'part2.pdf','readings':[reading(page=2,minute=620,slot=15)]}]
    result = audit(docs,csv=b'Reading,10:00 AM,10:15 AM\nWeight,75.4,76').json()
    assert result['aligned']
    assert [r['status'] for r in result['rows']] == ['match','mismatch']
    assert not audit(list(reversed(docs)),csv=b'Reading,10:00 AM,10:15 AM\nWeight,75.4,76').json()['aligned']


def test_bad_extraction_and_csv():
    assert audit([]).status_code == 422
    assert audit([{'name':'x','readings':[{'page':100}]}]).status_code == 422
    assert audit([{'name':'x','readings':[reading()]}],csv=b'invalid').status_code == 422
    assert client.post('/api/compare').status_code == 422


def test_extraction_without_csv_and_global_page_references(monkeypatch):
    with pymupdf.open() as doc:
        doc.new_page()
        pdf = doc.tobytes()
    monkeypatch.setattr('app.services.pipeline.make_engine',lambda: object())
    monkeypatch.setattr('app.services.pipeline.extract_page',lambda engine,image,page:[reading(page)])
    result = extract_documents([('first.pdf',pdf),('second.pdf',pdf)])
    assert [doc['name'] for doc in result['documents']] == ['first.pdf','second.pdf']
    assert [doc['readings'][0]['page'] for doc in result['documents']] == [1,2]
    assert [doc['readings'][0]['local_page'] for doc in result['documents']] == [1,1]
    assert result['documents'][1]['readings'][0]['document_name'] == 'second.pdf'
    assert 'rows' not in result


def test_extract_upload_validation():
    assert client.post('/api/extract').status_code == 422
    assert client.post('/api/extract',files={'pdfs':('bad.pdf',b'bad')}).status_code == 422
    assert client.post('/api/extract',files={'pdfs':('bad.txt',b'bad')}).status_code == 422


def test_source_confirmation_validates_before_continuing():
    result = client.post('/api/source', files={'source':('source.csv', b'Reading,10:00 AM\nWeight,75.4')})
    assert result.status_code == 200
    assert result.json() == {'reading_count':1, 'field_count':1}
    assert result.headers['cache-control'] == 'no-store'
    assert client.post('/api/source', files={'source':('bad.csv', b'not a source matrix')}).status_code == 422
    assert client.post('/api/source', files={'source':('bad.txt', b'Reading,10:00 AM\nWeight,75.4')}).status_code == 422
    assert client.post('/api/source').status_code == 422
    assert client.post('/api/source', files={'source':('empty.csv', b'')}).status_code == 413
