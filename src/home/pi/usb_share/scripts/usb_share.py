#!/usr/bin/python3
"""Debounce writes without losing events arriving during a USB reconnect."""
import logging
import subprocess
import threading
import time
from usb_share_common import BASE, storage_lock, usb_control


class DirtyState:
    def __init__(self):
        self.lock = threading.Lock()
        self.generation = 0
        self.completed = 0
        self.changed = 0

    def mark(self):
        with self.lock:
            self.generation += 1
            self.changed = time.monotonic()

    def ready(self, delay=25):
        with self.lock:
            if self.generation != self.completed and time.monotonic() - self.changed >= delay:
                return self.generation
        return None

    def finish(self, generation):
        with self.lock:
            self.completed = generation


def main():
    import fcntl
    from usb_share_common import RUN
    # Older images may still start the compatibility entry point from another unit.
    singleton = (RUN / 'watcher.lock').open('a')
    try:
        fcntl.flock(singleton, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        singleton.close()
        return
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    state = DirtyState()

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if event.event_type in ('created', 'modified', 'deleted', 'moved', 'closed'):
                state.mark()

    observer = Observer()
    observer.schedule(Handler(), str(BASE / 'upload'), recursive=True)
    observer.start()
    state.mark()
    try:
        while True:
            generation = state.ready()
            if generation is not None:
                try:
                    with storage_lock(blocking=False):
                        usb_control('reset')
                    state.finish(generation)
                except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    logging.warning('USB refresh deferred: %s', exc)
                    time.sleep(5)
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()
        singleton.close()


if __name__ == '__main__':
    main()
