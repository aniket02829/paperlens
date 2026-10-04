import io

from tests.conftest import make_pdf


def test_index_has_security_headers(app_client):
    response = app_client.get('/')
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers['Content-Security-Policy']
    assert response.headers['X-Content-Type-Options'] == 'nosniff'


def test_health(app_client):
    assert app_client.get('/health').get_json()['status'] == 'healthy'


def test_stats_counts_real_rows(app_client):
    stats = app_client.get('/stats').get_json()
    assert stats['journals'] > 30000 and stats['conferences'] > 900


def test_analyze_rejects_fake_pdf(app_client):
    data = {'file': (io.BytesIO(b'MZ this is an exe'), 'paper.pdf')}
    response = app_client.post('/analyze', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert "don't match" in response.get_json()['error']


def test_analyze_rejects_doc_with_advice(app_client):
    data = {'file': (io.BytesIO(b'\xd0\xcf\x11\xe0'), 'paper.doc')}
    response = app_client.post('/analyze', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert '.docx' in response.get_json()['error']


def test_analyze_real_pdf(app_client, tmp_path, fake_apis):
    fake_apis.crossref['10.1016/j.patcog.2020.107404'] = {'type': 'journal-article', 'issn': ['0031-3203'],
                                                         'container-title': 'Pattern Recognition'}
    path = make_pdf(tmp_path / 'p.pdf', ['https://doi.org/10.1016/j.patcog.2020.107404'],
                    title='Nested U-Structures for Salient Object Detection')
    with open(path, 'rb') as f:
        response = app_client.post('/analyze', data={'file': (f, 'p.pdf')}, content_type='multipart/form-data')
    body = response.get_json()
    assert body['success'] and body['result']['quartile'] == 'Q1'
    assert body['result']['filename'] == 'p.pdf'


def test_bulk_mixes_good_and_bad_files(app_client, tmp_path):
    path = make_pdf(tmp_path / 'p.pdf', ['Proceedings of the Workshop on Things'], title='A Workshop Paper Title')
    with open(path, 'rb') as f:
        data = {'files': [(f, 'good.pdf'), (io.BytesIO(b'nope'), 'bad.pdf')]}
        body = app_client.post('/analyze-bulk', data=data, content_type='multipart/form-data').get_json()
    assert body['summary']['successful'] == 1
    assert body['summary']['failed'] == 1


def test_lookup_endpoint(app_client, fake_apis):
    fake_apis.crossref['10.1109/cvpr.2016.90'] = {'type': 'proceedings-article', 'container-title': 'CVPR'}
    body = app_client.post('/api/lookup', json={'query': 'https://doi.org/10.1109/CVPR.2016.90'}).get_json()
    assert body['success'] and body['result']['category'] == 'conference'


def test_lookup_validation(app_client):
    assert app_client.post('/api/lookup', json={'query': ''}).status_code == 400
    assert app_client.post('/api/lookup', json={'query': 'x' * 501}).status_code == 400
    assert app_client.post('/api/lookup', json={'query': 'short'}).status_code == 400


def test_journal_search_and_compare(app_client):
    body = app_client.get('/api/journals/search?q=pattern recognition&quartile=Q1').get_json()
    assert body['total'] >= 1
    first = body['results'][0]
    assert first['quartile'] == 'Q1' and isinstance(first['categories'], list)

    by_issn = app_client.get('/api/journals/search?q=0031-3203').get_json()
    assert by_issn['results'][0]['title'] == 'Pattern Recognition'

    ids = ','.join(str(r['id']) for r in body['results'][:2])
    compared = app_client.get(f'/api/journals?ids={ids}').get_json()
    assert len(compared['results']) == min(2, len(body['results']))


def test_journal_search_handles_wildcards(app_client):
    body = app_client.get('/api/journals/search?q=%25%25%25').get_json()
    assert body['total'] == 0


def test_areas_and_suggest(app_client):
    assert 'Computer Science' in app_client.get('/api/journals/areas').get_json()['areas']
    suggest = app_client.get('/api/journals/suggest?field=Artificial Intelligence').get_json()
    assert len(suggest['results']) == 10


def test_unknown_api_route_is_json_404(app_client):
    response = app_client.get('/api/nope')
    assert response.status_code == 404 and response.get_json()['success'] is False
