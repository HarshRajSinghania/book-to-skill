"""BeautifulSoup HTML and EPUB extraction must not split inline text nodes."""
import sys
from pathlib import Path
import pytest
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from book_to_skill.parsers.html import _HTMLTextExtractor, extract_html_content
from book_to_skill.utils import detect_structure
pytest.importorskip("bs4")
STYLED = ("<html><body><h2>Chapter <span>1</span>: Syntax</h2>"
          "<p>A hyper<span>text</span> term remains continuous.</p>"
          "<h2>Chapter <span>2</span>: Safety</h2>"
          "<p>Only retry when the failure is temporary.</p></body></html>")
PLAIN = STYLED.replace("<span>", "").replace("</span>", "")

def _stdlib(fragment):
    parser = _HTMLTextExtractor()
    parser.feed(fragment)
    return parser.get_text()

def test_styled_heading_matches_plain_and_stdlib():
    styled = extract_html_content(STYLED)
    plain = extract_html_content(PLAIN)
    assert "hyper
text" not in styled
    assert "hypertext" in styled and "Chapter 1: Syntax" in styled
    assert detect_structure(styled)["chapters_detected"] == 2
    assert detect_structure(plain)["chapters_detected"] == 2
    assert detect_structure(_stdlib(STYLED))["chapters_detected"] == 2

def test_highlighted_code_keeps_indentation():
    code = "<pre><code>if enabled:
    <span>print</span>("ok")
</code></pre>"
    extracted = extract_html_content(code)
    assert extracted == "if enabled:
    print("ok")
"
    compile(extracted, "<synthetic-not-executed>", "exec")

def test_leading_spaces_and_nested_spans_stay_on_the_line():
    raw = "<pre><code>  <span>return <b>value</b></span>
</code></pre>"
    assert extract_html_content(raw) == "  return value
"

def test_block_list_and_table_boundaries_remain():
    raw = ("<h2>Chapter 1</h2><p>Body</p><p>line one<br>line two</p>"
           "<ul><li>alpha</li><li>beta</li></ul>"
           "<table><tr><td>Chapter 2</td><td>Models</td></tr></table>")
    extracted = extract_html_content(raw)
    assert "Chapter 1
Body" in extracted
    assert "line one
line two" in extracted
    assert "alpha
beta" in extracted
    assert "Chapter 2	Models" in extracted
    assert detect_structure(extracted)["chapters_detected"] == 2

def test_inline_markup_and_entities_do_not_add_separators():
    raw = '<p>see <b>bold</b> <i>italic</i> <a href="#x">chapter 4</a> & more</p>'
    assert extract_html_content(raw) == "see bold italic chapter 4 & more"

def test_script_and_style_still_stripped():
    raw = "<html><head><title>ignored</title></head><body><style>x{}</style><p>kept</p><script>nope()</script></body></html>"
    extracted = extract_html_content(raw)
    assert "kept" in extracted and "nope" not in extracted and "ignored" not in extracted and "x{}" not in extracted

pytest.importorskip("ebooklib")

def test_ebooklib_keeps_inline_chapter_text(tmp_path):
    from ebooklib import epub
    from book_to_skill.parsers.epub import extract_with_ebooklib, extract_with_zipfile
    book = epub.EpubBook()
    book.set_identifier("synthetic-inline-continuity")
    book.set_title("Synthetic continuity")
    book.set_language("en")
    chapters = []
    for number, title in [(1, "Syntax"), (2, "Safety")]:
        chapter = epub.EpubHtml(title=title, file_name="c%s.xhtml" % number, lang="en")
        chapter.content = ("<h2>Chapter <span>%s</span>: %s</h2>"
                           "<p>A hyper<span>text</span> term remains continuous.</p>") % (number, title)
        book.add_item(chapter)
        chapters.append(chapter)
    book.toc = tuple(chapters)
    book.add_item(epub.EpubNav())
    book.spine = chapters
    path = tmp_path / "inline-continuity.epub"
    epub.write_epub(str(path), book)
    preferred = extract_with_ebooklib(str(path))
    fallback = extract_with_zipfile(str(path))
    assert preferred is not None
    assert "hyper
text" not in preferred and "hypertext" in preferred
    assert detect_structure(preferred)["chapters_detected"] == 2
    assert detect_structure(fallback)["chapters_detected"] == 2
