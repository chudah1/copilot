from app.services.text_cleaning import clean_text


def test_clean_text_turns_html_paragraphs_into_readable_blocks() -> None:
    source = "<body><p>First&nbsp;paragraph.</p><p>Second <strong>paragraph</strong>.</p></body>"

    assert clean_text(source) == "First paragraph.\n\nSecond paragraph."


def test_clean_text_leaves_plain_text_readable() -> None:
    assert clean_text("A plain summary.\\nSecond line.") == "A plain summary.\nSecond line."
