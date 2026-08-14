from knowledge_base.adapters.chunkers.text import MarkdownChunker, PlainTextChunker
from knowledge_base.adapters.parsers.text import MarkdownParser
from knowledge_base.application.file_classifier import FileClassifier
from knowledge_base.domain.models import SourceFile


def test_classifier_selects_supported_text_and_excludes_vendor() -> None:
    classifier = FileClassifier()

    assert classifier.classify("docs/guide.md") == "markdown"
    assert classifier.classify("README") == "markdown"
    assert classifier.classify("Dockerfile") == "plain_text"
    assert classifier.classify("src/app.py") == "plain_text"
    assert classifier.classify("vendor/readme.md") is None
    assert classifier.classify("assets/logo.png") is None


def test_markdown_chunker_preserves_heading_context_and_stable_ids() -> None:
    source = SourceFile(
        repository_id="owner/repo",
        path="docs/orders.md",
        ref="abc123",
        content=(
            "# Orders\nOverview\n\n"
            "## Search\ncustomer_id start_date end_date\n\n"
            "### Database\norders customers"
        ),
    )
    document = MarkdownParser().parse(source)
    chunker = MarkdownChunker(max_tokens=20, overlap_tokens=2)

    first = chunker.chunk(document)
    second = chunker.chunk(document)

    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert [chunk.heading_path for chunk in first] == [
        ("Orders",),
        ("Orders", "Search"),
        ("Orders", "Search", "Database"),
    ]
    assert first[1].start_line == 4
    assert first[1].metadata["path"] == "docs/orders.md"


def test_plain_text_chunker_splits_chinese_without_spaces_with_overlap() -> None:
    source = SourceFile("owner/repo", "notes.txt", "abc123", "甲乙丙丁戊己庚辛")
    document = MarkdownParser().parse(source)
    chunker = PlainTextChunker(max_tokens=4, overlap_tokens=1)

    chunks = chunker.chunk(document)

    assert [chunk.content for chunk in chunks] == ["甲乙丙丁", "丁戊己庚", "庚辛"]
    assert [chunk.token_count for chunk in chunks] == [4, 4, 2]
