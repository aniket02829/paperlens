"""Classification decisions, using the real ranking database and faked API responses."""
from classifier.classifier import parse_identifier, acronym_candidates, clean_venue_name
from tests.conftest import make_pdf


def test_parse_identifier_variants():
    assert parse_identifier('10.1016/j.patcog.2020.107404')['doi'] == '10.1016/j.patcog.2020.107404'
    assert parse_identifier('https://doi.org/10.1109/CVPR.2016.90')['doi'] == '10.1109/CVPR.2016.90'
    assert parse_identifier('https://arxiv.org/abs/1706.03762v7')['arxiv_id'] == '1706.03762v7'
    assert parse_identifier('https://arxiv.org/pdf/1706.03762.pdf')['arxiv_id'] == '1706.03762'
    assert parse_identifier('arXiv:1512.03385')['arxiv_id'] == '1512.03385'
    assert parse_identifier('https://doi.org/10.48550/arXiv.1706.03762')['arxiv_id'] == '1706.03762'
    assert parse_identifier('  Attention is   all you need ')['title'] == 'Attention is all you need'


def test_acronyms_skip_publishers():
    names = ['2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)', "NeurIPS'23"]
    found = acronym_candidates(*names)
    assert 'CVPR' in found and 'NeurIPS' in found and 'IEEE' not in found


def test_clean_venue_name():
    assert clean_venue_name('Proceedings of the 34th International Conference on Machine Learning (ICML 2017)') == \
        'International Conference on Machine Learning'


def test_journal_by_doi(classifier, fake_apis):
    doi = '10.1016/j.patcog.2020.107404'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'container-title': 'Pattern Recognition',
                               'issn': ['0031-3203'], 'title': 'U2-Net', 'publisher': 'Elsevier BV'}
    fake_apis.openalex[doi] = {'type': 'article', 'source_type': 'journal', 'source_name': 'Pattern Recognition',
                               'is_in_doaj': False, 'is_oa': False}
    result = classifier.lookup(doi)
    assert result['category'] == 'journal'
    assert result['quartile'] == 'Q1'
    assert result['venue'] == 'Pattern Recognition'
    assert result['in_sjr'] is True
    assert result['trust']['warnings'] == []
    assert result['confidence'] >= 0.85


def test_conference_gets_core_rank_and_type(classifier, fake_apis):
    doi = '10.1109/cvpr.2016.90'
    fake_apis.crossref[doi] = {'type': 'proceedings-article', 'title': 'Deep Residual Learning',
                               'container-title': '2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)',
                               'publisher': 'IEEE'}
    result = classifier.lookup(doi)
    assert result['category'] == 'conference'
    assert result['core_rank'] == 'A*'
    assert result['conference_type'] == 'IEEE'


def test_international_is_not_mistaken_for_national(classifier, fake_apis):
    doi = '10.1007/978-3-319-24574-4_28'
    fake_apis.crossref[doi] = {'type': 'book-chapter', 'container-title': 'Lecture Notes in Computer Science',
                               'event': 'International Conference on Medical Image Computing and Computer-Assisted Intervention',
                               'publisher': 'Springer International Publishing'}
    result = classifier.lookup(doi)
    assert result['category'] == 'conference'
    assert result['conference_type'] == 'International'
    assert result['core_rank'] == 'A'
    assert 'Lecture Notes' not in result['venue']


def test_arxiv_preprint_without_published_version(classifier, fake_apis):
    fake_apis.s2['arxiv:2401.99999'] = {'title': 'A Fresh Preprint', 'venue': 'arXiv.org',
                                        'fieldsOfStudy': ['Computer Science']}
    result = classifier.lookup('arXiv:2401.99999')
    assert result['category'] == 'arxiv'
    assert result['is_arxiv']
    assert result['suggested_journals']
    assert all(j['sjr_score'] is not None for j in result['suggested_journals'])


def test_arxiv_paper_published_at_conference(classifier, fake_apis):
    fake_apis.s2['arxiv:1512.03385'] = {
        'title': 'Deep Residual Learning for Image Recognition', 'venue': 'Computer Vision and Pattern Recognition',
        'publicationVenue': {'name': 'Computer Vision and Pattern Recognition', 'type': 'conference',
                             'alternate_names': ['CVPR']},
        'externalIds': {'ArXiv': '1512.03385', 'DOI': '10.1109/cvpr.2016.90'}}
    fake_apis.crossref['10.1109/cvpr.2016.90'] = {'type': 'proceedings-article', 'publisher': 'IEEE',
                                                  'container-title': '2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)'}
    result = classifier.lookup('https://arxiv.org/abs/1512.03385')
    assert result['category'] == 'conference'
    assert result['is_arxiv'] is True
    assert result['published_doi'] == '10.1109/cvpr.2016.90'
    assert result['core_rank'] == 'A*'


def test_unknown_journal_gets_trust_warning(classifier, fake_apis):
    doi = '10.9999/fake.123'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'container-title': 'Global Journal of Everything Studies'}
    fake_apis.openalex[doi] = {'source_type': 'journal', 'is_in_doaj': False}
    result = classifier.lookup(doi)
    assert result['category'] == 'journal'
    assert result['quartile'] == 'Unranked'
    assert 'not_in_sjr_or_doaj' in result['trust']['warnings']


def test_retracted_paper_is_flagged(classifier, fake_apis):
    doi = '10.1016/j.patcog.2020.000001'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'issn': ['0031-3203']}
    fake_apis.openalex[doi] = {'source_type': 'journal', 'is_retracted': True}
    result = classifier.lookup(doi)
    assert result['is_retracted'] is True
    assert 'retracted' in result['trust']['warnings']


def test_title_not_found(classifier):
    result = classifier.lookup('a title that no database has ever heard of')
    assert result['category'] == 'unknown'
    assert result['error']


def test_text_only_pdf_uses_heuristics(classifier, tmp_path):
    path = make_pdf(tmp_path / 'p.pdf', [
        'R. Sharma', 'Proceedings of the National Conference on Emerging Trends 2023',
        'Abstract: We survey things.'], title='A Survey of Emerging Trends in Computing')
    result = classifier.classify(path)
    assert result['category'] == 'conference'
    assert result['conference_type'] == 'National'
    assert result['confidence'] < 0.7


def test_scanned_pdf_gives_helpful_error(classifier, tmp_path):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.output(str(tmp_path / 'blank.pdf'))
    result = classifier.classify(str(tmp_path / 'blank.pdf'))
    assert result['category'] == 'error'
    assert 'DOI' in result['error']


def test_every_result_has_the_same_keys(classifier, fake_apis, tmp_path):
    fake_apis.crossref['10.1016/j.patcog.2020.107404'] = {'type': 'journal-article', 'issn': ['0031-3203']}
    journal = classifier.lookup('10.1016/j.patcog.2020.107404')
    preprint = classifier.lookup('arXiv:2401.99999')
    unknown = classifier.lookup('a title that no database has ever heard of')
    error = classifier._error_result('x')
    keys = set(journal)
    for other in (preprint, unknown, error):
        assert keys <= set(other) | {'filename'}, keys - set(other)


def test_arxiv_api_fills_in_when_semantic_scholar_is_down(classifier, fake_apis):
    fake_apis.arxiv['2310.06825'] = {'title': 'Mistral 7B', 'authors': 'Albert Q. Jiang', 'year': 2023,
                                     'primary_category': 'cs.CL', 'abstract': 'We introduce Mistral 7B.'}
    result = classifier.lookup('https://arxiv.org/abs/2310.06825')
    assert result['category'] == 'arxiv'
    assert result['title'] == 'Mistral 7B'
    assert result['authors'] == 'Albert Q. Jiang'
    assert result['suggestion_field'] == 'Artificial Intelligence'
    assert all(j['quartile'] in ('Q1', 'Q2', 'Q3', 'Q4') for j in result['suggested_journals'])


def test_arxiv_doi_field_reveals_published_version(classifier, fake_apis):
    fake_apis.arxiv['1234.56789'] = {'title': 'Some Paper', 'doi': '10.1016/j.patcog.2020.107404'}
    fake_apis.crossref['10.1016/j.patcog.2020.107404'] = {'type': 'journal-article', 'issn': ['0031-3203']}
    result = classifier.lookup('arXiv:1234.56789')
    assert result['category'] == 'journal' and result['is_arxiv'] and result['quartile'] == 'Q1'


def test_rate_limited_source_is_paused_not_waited_on(monkeypatch):
    """OpenAlex can answer 429 with Retry-After: 46000. We must not sleep on it."""
    import time
    from classifier.metadata_fetcher import MetadataFetcher, MAX_PAUSE_SECONDS

    class Response:
        status_code = 429
        headers = {'Retry-After': '46505'}

    calls = []
    fetcher = MetadataFetcher('test@example.com')
    monkeypatch.setattr(fetcher.session, 'get', lambda *a, **k: calls.append(1) or Response())
    start = time.time()
    assert fetcher._get_json('https://api.openalex.org/works', {'search': 'x'}) is None
    assert fetcher._get_json('https://api.openalex.org/works', {'search': 'y'}) is None
    assert time.time() - start < 1
    assert len(calls) == 1  # the second call was skipped during the pause
    assert fetcher._cooldown_until['api.openalex.org'] - time.time() <= MAX_PAUSE_SECONDS


def test_wrapped_venue_line_finds_core_rank(classifier, tmp_path):
    """No DOI, and the venue name wraps onto a second line, as in PMLR papers."""
    path = make_pdf(tmp_path / 'p.pdf', [
        'Proceedings of the 40th International Conference on Machine',
        'Learning, Honolulu, Hawaii, USA. PMLR 202, 2023.',
        'Abstract: We study things.'], title='A Study of Gradient Things in Deep Networks')
    result = classifier.classify(path)
    assert result['category'] == 'conference'
    assert result['core_rank'] == 'A*' and result['core_acronym'] == 'ICML'


def test_hyphenated_venue_line_finds_acronym(classifier, tmp_path):
    path = make_pdf(tmp_path / 'p.pdf', [
        'Proceedings of the 26th International Conference on Artificial Intel-',
        'ligence and Statistics (AISTATS) 2023, Valencia, Spain.',
        'Abstract: We study things.'], title='Bayesian Optimisation of Expensive Things')
    result = classifier.classify(path)
    assert result['core_rank'] == 'A' and result['core_acronym'] == 'AISTATS'


def test_pmlr_series_name_is_not_read_as_icml(classifier, tmp_path):
    path = make_pdf(tmp_path / 'p.pdf', [
        'Proceedings of Machine Learning Research vol 195:1-55, 2023 36th Annual Conference on Learning Theory',
        'Abstract: We prove things.'], title='Lower Bounds for Learning Hard Things')
    result = classifier.classify(path)
    assert result['core_acronym'] == 'COLT'


def test_scopus_discontinued_journal_is_flagged(classifier, fake_apis):
    # Alexandria Engineering Journal is still Q1 in SJR 2025 but Scopus discontinued it in 2025.
    doi = '10.1016/j.aej.2024.00001'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'container-title': 'Alexandria Engineering Journal',
                               'issn': ['1110-0168'], 'title': 'Some paper'}
    result = classifier.lookup(doi)
    assert result['category'] == 'journal' and result['quartile'] == 'Q1'
    assert result['scopus']['discontinued'] is True
    assert result['scopus']['discontinued_year'] == '2025'
    assert 'scopus_discontinued' in result['trust']['warnings']


def test_hijacked_clone_is_reported_with_authentic_url(classifier, fake_apis):
    doi = '10.5465/annals.2020.0001'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'container-title': 'Academy of Management Annals',
                               'issn': ['1941-6520'], 'title': 'A review'}
    result = classifier.lookup(doi)
    hijacked = result['watchlist']['hijacked']
    assert hijacked and hijacked['authentic_url'].startswith('https://journals.aom.org')
    assert 'hijacked_clone_exists' in result['trust']['warnings']
    assert result['quartile'] == 'Q1'  # the real journal's rank is unaffected


def test_predatory_list_matches_exact_names_only(classifier, fake_apis):
    doi = '10.9999/aeq.2020.1'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'container-title': 'Academic Exchange Quarterly',
                               'title': 'A paper', 'publisher': 'OMICS International'}
    result = classifier.lookup(doi)
    assert result['watchlist']['predatory_journal']['name'] == 'Academic Exchange Quarterly'
    assert result['watchlist']['predatory_publisher']['name'] == 'OMICS International'
    assert {'name_on_predatory_list', 'publisher_on_predatory_list'} <= set(result['trust']['warnings'])

    fake_apis.crossref['10.9999/x'] = {'type': 'journal-article', 'container-title': 'Academic Exchange Quarterly Review',
                                       'title': 'Another paper'}
    assert classifier.lookup('10.9999/x')['watchlist']['predatory_journal'] is None


def test_doaj_listing_comes_from_local_data(classifier, fake_apis):
    doi = '10.1371/journal.pone.0000001'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'container-title': 'PLoS ONE', 'issn': ['1932-6203'],
                               'title': 'A paper'}
    result = classifier.lookup(doi)
    assert result['doaj'] and result['doaj']['apc'] == 'Yes'
    assert result['trust']['in_doaj'] is True
    assert result['trust']['indexed_in_scopus'] is True


def test_unranked_venue_gets_openalex_statistics(classifier, fake_apis):
    doi = '10.9999/newj.2024.1'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'container-title': 'Brand New Journal of Things', 'title': 'A paper'}
    fake_apis.openalex[doi] = {'type': 'article', 'source_type': 'journal', 'source_name': 'Brand New Journal of Things',
                               'source_id': 'https://openalex.org/S999'}
    fake_apis.openalex_sources['https://openalex.org/S999'] = {'name': 'Brand New Journal of Things', 'h_index': 12,
                                                               'mean_citedness_2yr': 1.4, 'works_count': 300}
    result = classifier.lookup(doi)
    assert result['in_sjr'] is False
    assert result['venue_stats']['h_index'] == 12
    assert result['trust']['indexed_in_scopus'] is False
    assert 'not_in_sjr_or_doaj' in result['trust']['warnings']


def test_ranked_venue_skips_openalex_statistics(classifier, fake_apis):
    doi = '10.1016/j.patcog.2020.107404'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'container-title': 'Pattern Recognition', 'issn': ['0031-3203'],
                               'title': 'U2-Net'}
    fake_apis.openalex[doi] = {'type': 'article', 'source_type': 'journal', 'source_id': 'https://openalex.org/S1'}
    fake_apis.openalex_sources['https://openalex.org/S1'] = {'h_index': 300}
    assert classifier.lookup(doi)['venue_stats'] is None


def test_known_issn_outside_sjr_is_not_fuzzy_matched_to_a_similar_name(classifier, fake_apis):
    # JOSS (ISSN 2475-9066) is not in Scimago; 'Journal of Open Research Software' is, and is Q3.
    doi = '10.21105/joss.01686'
    fake_apis.crossref[doi] = {'type': 'journal-article', 'container-title': 'Journal of Open Source Software',
                               'issn': ['2475-9066'], 'title': 'A tool'}
    result = classifier.lookup(doi)
    assert result['category'] == 'journal'
    assert result['in_sjr'] is False
    assert result['quartile'] == 'Unranked'
    assert result['venue'] == 'Journal of Open Source Software'


def test_two_column_pdf_gets_core_rank_and_clean_venue_name(classifier, tmp_path):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.multi_cell(0, 10, 'Human-Timescale Adaptation in an Open-Ended Task Space', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', size=9)
    left = ['Abstract: foundation models adapt quickly.', 'Proceedings of the 40th International Conference on Machine',
            'Learning, Honolulu, Hawaii, USA. PMLR 202, 2023.']
    right = ['tive Agent (AdA), an agent capable of human-timescale', 'adaptation in a vast open-ended task space with sparse',
             'rewards and many held-out environments.']
    y = pdf.get_y() + 4
    for i, (l, r) in enumerate(zip(left, right)):
        pdf.set_xy(10, y + i * 6)
        pdf.cell(92, 6, l)
        pdf.set_xy(108, y + i * 6)
        pdf.cell(92, 6, r)
    pdf.output(str(tmp_path / 'cols.pdf'))
    result = classifier.classify(str(tmp_path / 'cols.pdf'))
    assert result['category'] == 'conference'
    assert result['core_acronym'] == 'ICML'
    assert result['venue'] == 'International Conference on Machine Learning'


def test_journal_name_in_header_identifies_the_journal(classifier, tmp_path):
    path = make_pdf(tmp_path / 'cjs.pdf', [
        '© Canadian Journal of Sociology 46(3) 2021 191',
        'Abstract: Despite changes to immigration policy, many newcomers face barriers.'],
        title='Should I Stay or Should I Go Home')
    result = classifier.classify(path)
    assert result['category'] == 'journal'
    assert result['venue'] == 'Canadian Journal of Sociology'
    assert result['quartile'] == 'Q4'


def test_scanned_pdf_is_refused_with_advice(classifier, tmp_path):
    from fpdf import FPDF
    from PIL import Image
    image = tmp_path / 'page.png'
    Image.new('RGB', (600, 800), 'white').save(image)
    pdf = FPDF()
    pdf.set_auto_page_break(False)
    for _ in range(2):
        pdf.add_page()
        pdf.image(str(image), x=10, y=10, w=190)
    pdf.set_font('Helvetica', size=8)
    pdf.set_xy(10, 280)
    pdf.cell(0, 5, '1 Universidad de Sevilla benitosm@us.es')
    pdf.output(str(tmp_path / 'scan.pdf'))
    result = classifier.classify(str(tmp_path / 'scan.pdf'))
    assert result['category'] == 'error'
    assert 'scanned' in result['error']


def test_title_search_prefers_the_published_version(monkeypatch):
    from classifier.metadata_fetcher import MetadataFetcher, CROSSREF_URL
    fetcher = MetadataFetcher('test@example.com')
    preprint = {'title': ['Should ChatGPT be biased?'], 'type': 'posted-content', 'DOI': '10.2139/ssrn.1',
                'relation': {'is-preprint-of': [{'id': '10.5210/fm.1', 'id-type': 'doi'}]}}
    article = {'title': ['Should ChatGPT be biased?'], 'type': 'journal-article', 'DOI': '10.5210/fm.1',
               'container-title': ['First Monday'], 'ISSN': ['1396-0466']}
    responses = {CROSSREF_URL: {'message': {'items': [preprint, article]}},
                 f'{CROSSREF_URL}/10.5210/fm.1': {'message': article}}
    monkeypatch.setattr(fetcher, '_get_json', lambda url, params=None, headers=None, label='': responses.get(url))
    assert fetcher.fetch_by_title('Should ChatGPT be biased?')['doi'] == '10.5210/fm.1'

    # Only the preprint is returned by the search: follow its link to the published version.
    responses[CROSSREF_URL] = {'message': {'items': [preprint]}}
    assert fetcher.fetch_by_title('Should ChatGPT be biased?')['container-title'] == 'First Monday'


def test_journal_name_inside_a_conference_name_is_not_journal_evidence(classifier, tmp_path):
    # 'Language Resources and Evaluation' is an SJR journal; LREC is a conference.
    path = make_pdf(tmp_path / 'lrec.pdf', [
        'Proceedings of the 13th Language Resources and Evaluation Conference, pages 1403-1412',
        'Marseille, 20-25 June 2022. European Language Resources Association (ELRA)',
        'Abstract: We release a corpus.'], title='A Corpus for Something Useful in Many Languages')
    result = classifier.classify(path)
    assert result['category'] == 'conference'
    assert result['core_acronym'] == 'LREC'


def test_unstamped_preprint_is_found_on_arxiv_by_title(classifier, fake_apis, tmp_path):
    """arXiv sometimes serves the authors' own PDF without the margin stamp."""
    title = 'PlainMap: a lightweight, restartable mapping pipeline for ancient and modern DNA'
    path = make_pdf(tmp_path / 'plain.pdf', ['Michael V Wesbury', 'Abstract: We present a mapping pipeline.'], title=title)
    fake_apis.arxiv_titles[title.lower()] = {'arxiv_id': '2609.18372v1', 'title': title, 'primary_category': 'q-bio.GN'}
    result = classifier.classify(path)
    assert result['category'] == 'arxiv'
    assert result['arxiv_id'] == '2609.18372v1'
    assert result['suggestion_field']


def test_isbn_alone_does_not_make_a_conference(classifier, tmp_path):
    path = make_pdf(tmp_path / 'issue.pdf', ['ISBN 978-84697-9697-9', 'Abstract: An essay about history.'],
                    title='An Essay About the History of Something')
    assert classifier.classify(path)['category'] == 'unknown'


def test_published_copy_found_on_arxiv_by_title_stays_a_conference_paper(classifier, fake_apis, tmp_path):
    """A PMLR paper has no DOI; its arXiv twin is found by title, but the PDF says 'Proceedings of'."""
    title = 'Lower Bounds for Learning Hard Things'
    path = make_pdf(tmp_path / 'colt.pdf', [
        'Proceedings of Machine Learning Research vol 195:1-55, 2023 36th Annual Conference on Learning Theory',
        'Abstract: We prove things.'], title=title)
    fake_apis.arxiv_titles[title.lower()] = {'arxiv_id': '2302.00001v1', 'title': title, 'primary_category': 'cs.LG'}
    result = classifier.classify(path)
    assert result['category'] == 'conference'
    assert result['core_acronym'] == 'COLT'
    assert result['is_arxiv'] and result['arxiv_id'] == '2302.00001v1'
