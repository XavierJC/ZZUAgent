"""Single bounded consumer under the application document-root lock."""
from threading import Event,Thread

class ExtractionCoordinator:
    def __init__(self,factory):
        self.factory,self.stop=factory,Event()
        with factory() as service:service.recover()
        self.thread=Thread(target=self.work,daemon=True,name='eduagent-question-extraction');self.thread.start()

    def work(self):
        while not self.stop.is_set():
            try:
                with self.factory() as service:row=service.claim()
                if row:
                    with self.factory() as service:service.execute(row,self.stop)
                    continue
            except Exception:pass
            self.stop.wait(.3)

    def close(self):
        self.stop.set();self.thread.join(timeout=60)
        if self.thread.is_alive():raise RuntimeError('提取任务尚未结束，请保持资料目录锁')
