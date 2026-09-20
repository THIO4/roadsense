"""One place to configure logging for every entry point (collector, API)."""

import logging


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Library loggers are far too chatty at INFO: the Cosmos SDK logs every HTTP request
    # and its headers (~2 KB each, 1000+ per run). In the cloud every line costs storage
    # and buries our own messages. Our own loggers keep the requested level.
    for noisy in ("azure", "httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
