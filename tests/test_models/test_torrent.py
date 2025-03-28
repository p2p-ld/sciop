def test_torrent_max_size_from_config():
    """
    Torrent class shouldn't have its own independent max size.

    Remove this once we replace torf
    """
    from sciop.config import config
    from sciop.models import Torrent

    assert config.upload_limit == Torrent.MAX_TORRENT_FILE_SIZE
