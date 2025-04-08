from sciop.services.docs import build_docs


def test_docs_debounce(capsys):
    """
    Docs should not build twice if they have been built in the last 10 seconds
    :param capsys:
    :return:
    """
    build_docs()
    build_docs()
    captured = capsys.readouterr()
    assert "Not rebuilding" in captured.out
