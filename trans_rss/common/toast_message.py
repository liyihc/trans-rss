import weakref
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from threading import Thread
from time import sleep
from typing import List, Literal

from trans_rss.logger import logger
from trans_rss.config import config

TAG = "Common"


@dataclass
class ToastMessage:
    content: str
    duration: int
    position: Literal["left", "center", "right"]
    color: Literal["info", "error", "warn", "success"]


input_queue: Queue[ToastMessage] = Queue()
queues: List[weakref.ReferenceType[Queue[ToastMessage]]] = []


def emit_message(
        content: str, duration: int = 2,
        position: Literal["left", "center", "right"] = "center",
        color: Literal["info", "error", "warn", "success"] = "info"):
    input_queue.put(ToastMessage(content, duration, position, color))


emit_thread: Thread = None


def start_emit():
    def emitter():
        invalid = []
        while True:
            msg = input_queue.get()
            logger.debug(TAG, f"start_emit queue {queues}")
            for index, ref in enumerate(queues):
                queue = ref()
                if queue is not None and queue.qsize() < 20:
                    queue.put(msg)
                else:
                    invalid.append(index)
            queue = None
            if invalid:
                list(map(queues.pop, reversed(invalid)))
            invalid.clear()
            sleep(.5)
    global emit_thread
    emit_thread = Thread(target=emitter, daemon=True)
    emit_thread.start()


v_thread: Thread = None


def start_v():
    def v():
        while True:
            emit_message(
                f"{datetime.now().replace(microsecond=0)} | peers {len(queues)}")
            sleep(5)
    global v_thread
    v_thread = Thread(target=v, daemon=True)
    v_thread.start()


if config.logger_level == "VERBOSE":
    start_v()
