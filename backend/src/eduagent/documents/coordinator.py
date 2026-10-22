"""One durable local queue consumer, with no shared SQLite connections."""

from threading import Event, Thread
from eduagent.documents.limits import WorkerLock


class DocumentCoordinator:
    def __init__(self, service_factory, root, runner=None, vision_factory=None):
        self.factory, self.runner, self.vision_factory = service_factory, runner, vision_factory
        self.stop = Event()
        self.lock = WorkerLock(root)
        try:
            with self.factory() as service:
                service.recover()
        except BaseException:
            self.lock.close()
            raise
        self.thread = Thread(target=self._work, daemon=True, name='eduagent-document-parser')
        self.thread.start()

    def _work(self):
        while not self.stop.is_set():
            try:
                with self.factory() as service:
                    run = service.claim()
                if run:
                    with self.factory() as service:
                        service.execute(run, self.runner, self.vision_factory, self.stop)
                    continue
            except Exception:
                # Raw parsing/storage exceptions never contain public log text.
                pass
            self.stop.wait(.25)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=60)
        if self.thread.is_alive():
            raise RuntimeError('解析任务尚未结束，未释放目录锁')
        self.lock.close()
