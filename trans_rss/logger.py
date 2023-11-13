from dataclasses import dataclass
from datetime import datetime
import json
import logging
import logging.handlers
import os
import pathlib
import sys
from typing import Literal


from .config import log_dir, config

api = log_dir / "interactive"
update = log_dir / "update"
exception = log_dir / "exception"
trans_rss = log_dir / "trans-rss"

for dir in [log_dir, api, update, exception, trans_rss]:
    dir.mkdir(parents=True, exist_ok=True)

fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")


def init_logger(name: str, folder: pathlib.Path, stream=sys.stdout):
    logger = logging.getLogger(name)
    handler = logging.handlers.TimedRotatingFileHandler(
        folder / "log", when="midnight", encoding='utf-8')
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    shandler = logging.StreamHandler(stream)
    shandler.setFormatter(fmt)
    logger.addHandler(shandler)
    return logger


_update_logger = init_logger("update", update)
_update_logger.setLevel(config.update_logger_level)
_logger = init_logger("trans-rss", trans_rss)
_logger.setLevel(config.logger_level)


@dataclass
class _Logger:
    logger: logging.Logger

    def _flog(self, TAG: str, content: str):
        return f"[{TAG}] {content}"

    def debug(self, TAG: str, content: str):
        """
        10
        """
        self.logger.debug(self._flog(TAG, content))

    def info(self, TAG: str, content: str):
        """
        20
        """
        self.logger.info(self._flog(TAG, content))

    def warn(self, TAG: str, content: str):
        """
        30
        """
        self.logger.warn(self._flog(TAG, content))

    def error(self, TAG: str, content: str):
        """
        40
        """
        self.logger.error(self._flog(TAG, content))

    def exception(self, TAG: str, content: str):
        """
        40
        """
        self.logger.exception(self._flog(TAG, content), stack_info=1)

    def critical(self, TAG: str, content: str):
        """
        50
        """
        self.logger.critical(self._flog(TAG, content))


update_logger = _Logger(_update_logger)
logger = _Logger(_logger)
