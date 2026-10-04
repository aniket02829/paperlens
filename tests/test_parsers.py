from classifier.pdf_parser import PDFParser
from classifier.docx_parser import DocxParser
from tests.conftest import make_pdf, make_docx


def test_pdf_title_comes_from_largest_text(tmp_path):
    path = make_pdf(tmp_path / 'p.pdf', [
        'Jane Doe, John Roe', 'Abstract: We propose a method.', 'DOI: 10.1016/j.patcog.2020.107404'
    ], title='Nested U-Structures for Salient Object Detection')
    parsed = PDFParser().parse(path)
    assert parsed['title'] == 'Nested U-Structures for Salient Object Detection'
    assert parsed['doi'] == '10.1016/j.patcog.2020.107404'
    assert parsed['page_count'] == 1
    assert 'We propose a method' in parsed['full_text']


def test_pdf_parser_survives_garbage(tmp_path):
    path = tmp_path / 'bad.pdf'
    path.write_bytes(b'%PDF-1.4 this is not really a pdf')
    parsed = PDFParser().parse(str(path))
    assert parsed['full_text'] == ''


def test_docx_parser_extracts_same_fields(tmp_path):
    path = make_docx(tmp_path / 'p.docx', [
        'Deep Learning for Crop Disease Detection', 'A. Kumar, B. Singh',
        'Abstract: We detect diseases.', 'Keywords: deep learning, agriculture',
        'Proceedings of the National Conference on Computing 2024', 'ISSN 1532-4435'
    ])
    parsed = DocxParser().parse(path)
    assert parsed['title'] == 'Deep Learning for Crop Disease Detection'
    assert parsed['has_proceedings']
    assert parsed['issn'] == '1532-4435'
    assert parsed['abstract'].startswith('We detect diseases')


def test_sideways_arxiv_stamp_is_read(tmp_path):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', size=12)
    with pdf.rotation(90, x=10, y=200):
        pdf.text(10, 200, 'arXiv:2610.02203v1 [cs.CV] 1 Oct 2026')
    pdf.set_xy(20, 20)
    pdf.multi_cell(0, 6, 'Embedding Prediction Helps Image Generation\nAbstract: We study things.')
    pdf.output(str(tmp_path / 'stamp.pdf'))
    parsed = PDFParser().parse(str(tmp_path / 'stamp.pdf'))
    assert parsed['arxiv_id'] == '2610.02203v1'
    assert parsed['has_arxiv_stamp']


def test_tightly_set_text_keeps_word_boundaries():
    # Regression: pdfplumber's default spacing merged "Proceedings of Machine Learning".
    from classifier.pdf_parser import X_TOLERANCE
    assert X_TOLERANCE < 3


def test_small_caps_title_is_read_as_whole_words(tmp_path):
    """Decorative initials are set larger than the rest of the word; the title must still read."""
    from fpdf import FPDF
    from classifier.pdf_parser import PDFParser
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(pdf.get_string_width('S'), 10, 'S')
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'hould I Stay or Should I Go Home', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(pdf.get_string_width('N'), 10, 'N')
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'ewcomer Employment Experiences', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', size=10)
    pdf.multi_cell(0, 6, 'Abstract: Despite changes to immigration policy, many newcomers face barriers.', new_x='LMARGIN', new_y='NEXT')
    pdf.output(str(tmp_path / 'caps.pdf'))
    title = PDFParser().parse(str(tmp_path / 'caps.pdf'))['title']
    assert title == 'Should I Stay or Should I Go Home Newcomer Employment Experiences'


def test_two_column_venue_footnote_is_read_column_by_column(tmp_path):
    from fpdf import FPDF
    from classifier.pdf_parser import PDFParser
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
    parsed = PDFParser().parse(str(tmp_path / 'cols.pdf'))
    assert 'Conference on Machine Learning, Honolulu' not in parsed['venue_context']   # interleaved reading
    assert 'Conference on Machine Learning, Honolulu' in parsed['venue_context_alt']


def test_scanned_front_pages_are_detected(tmp_path):
    from fpdf import FPDF
    from PIL import Image
    from classifier.pdf_parser import PDFParser
    image = tmp_path / 'page.png'
    Image.new('RGB', (600, 800), 'white').save(image)
    pdf = FPDF()
    pdf.set_auto_page_break(False)
    for footnote in ('1 Universidad de Sevilla benitosm@us.es', ''):
        pdf.add_page()
        pdf.image(str(image), x=10, y=10, w=190)
        if footnote:
            pdf.set_font('Helvetica', size=8)
            pdf.set_xy(10, 280)
            pdf.cell(0, 5, footnote)
    pdf.output(str(tmp_path / 'scan.pdf'))
    parsed = PDFParser().parse(str(tmp_path / 'scan.pdf'))
    assert parsed['looks_scanned'] is True
    assert parsed['title'] is None
