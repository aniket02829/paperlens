from classifier import text_metadata as tm


def test_valid_issn_checksum():
    assert tm.is_valid_issn('0031-3203')      # Pattern Recognition
    assert tm.is_valid_issn('1532-4435')      # JMLR
    assert tm.is_valid_issn('0001-527X')
    assert not tm.is_valid_issn('0031-3204')


def test_find_issn_prefers_labeled_and_skips_year_ranges():
    assert tm.find_issn('Copyright 2019-2020. Some text.') is None
    assert tm.find_issn('Vol 3 (2019-2020) ISSN: 1532-4435') == '1532-4435'
    assert tm.find_issn('print ISSN 0031 3203') == '0031-3203'


def test_clean_doi_strips_trailing_punctuation():
    assert tm.clean_doi('10.1016/j.patcog.2020.107404.') == '10.1016/j.patcog.2020.107404'
    assert tm.clean_doi('10.1000/abc(123)') == '10.1000/abc(123)'
    assert tm.clean_doi('10.1000/abc123),') == '10.1000/abc123'


def test_extract_metadata_flags():
    text = ('A Study of Things\nJane Doe, John Roe\nAbstract: We study things.\nKeywords: things, stuff\n'
            'Received: 3 March 2021; Accepted: 5 May 2021\nVol. 12 No. 3\n'
            '978-1-6654-4509-2/22/$31.00 ©2022 IEEE\narXiv:2101.00001v2 [cs.LG]')
    result = tm.empty_result()
    tm.extract_metadata(text, result)
    assert result['has_review_dates']
    assert result['has_volume_issue']
    assert result['has_ieee_conference_footer']
    assert result['arxiv_id'] == '2101.00001v2'
    assert result['abstract'].startswith('We study things')
    assert result['keywords'].startswith('things, stuff')


def test_abstract_heading_is_removed_case_insensitively():
    result = tm.empty_result()
    tm.extract_metadata('Title Line Here\nABSTRACT — This paper shows.\nIntroduction', result)
    assert result['abstract'] == 'This paper shows.'


def test_doi_broken_across_lines_is_rejoined():
    result = tm.empty_result()
    tm.extract_metadata('Citation: e0000583. https://doi.org/10.1371/journal.\npgph.0000583 in global health', result)
    assert result['doi'] == '10.1371/journal.pgph.0000583'
