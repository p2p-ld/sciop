import multiprocessing as mp

from sciop.logging import init_logger


def _process(q: mp.Queue) -> None:
    log1 = init_logger("tests.logging")
    log2 = init_logger("tests.logging")
    log3 = init_logger("tests.logging")
    log4 = init_logger("tests.logging")
    q.put((len(log4.handlers), [str(h) for h in log4.handlers]))


def test_mp_file_handler_deduplication():
    """
    When we init a logger in a subprocess, we need to log to a different file,
    but we should only make one file handler per file so we don't end up with a million files open
    """
    q = mp.Queue()

    p = mp.Process(target=_process, args=(q,))
    p.start()
    p.join()

    n_handlers, handlers = q.get()
    assert n_handlers == 2, handlers
