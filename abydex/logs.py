"""Log file in the data folder, so problems on users' machines can be diagnosed."""
from __future__ import annotations

import logging
import logging.handlers

from .catalog import user_dir

_done = False


def log_path():
    return user_dir() / "abydex.log"


def setup() -> logging.Logger:
    global _done
    log = logging.getLogger("abydex")
    if not _done:
        h = logging.handlers.RotatingFileHandler(log_path(), maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
        _done = True
    return log
