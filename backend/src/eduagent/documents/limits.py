"""Resource limits for local parsing. A failed limit setup never runs a parser."""

import ctypes
import os
from pathlib import Path
import subprocess
import sys
import time

from eduagent.documents.models import DocumentError, MAX_OUTPUT


class WindowsJob:
    def __init__(self, process, memory_mb=512, cpu_seconds=30):
        from ctypes import wintypes as w
        size = ctypes.c_size_t

        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', w.DWORD),
                        ('min_working', size), ('max_working', size), ('active', w.DWORD),
                        ('affinity', size), ('priority', w.DWORD), ('scheduling', w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]

        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('process_memory', size), ('job_memory', size),
                        ('peak_process', size), ('peak_job', size)]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        kernel.CreateJobObjectW.restype = w.HANDLE
        kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        kernel.SetInformationJobObject.restype = w.BOOL
        kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        kernel.AssignProcessToJobObject.restype = w.BOOL
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        self.kernel, self.handle = kernel, kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise DocumentError('parser_unavailable', 503)
        limits = Extended()
        limits.basic.flags = 0x2000 | 0x100 | 0x200 | 0x2 | 0x4 | 0x8
        # Windows venv python.exe is a launcher plus its interpreter child.
        limits.basic.active = 2
        limits.basic.process_time = cpu_seconds * 10_000_000
        limits.basic.job_time = cpu_seconds * 10_000_000
        limits.process_memory = limits.job_memory = memory_mb * 1024 * 1024
        if (not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                or not kernel.AssignProcessToJobObject(self.handle, w.HANDLE(int(process._handle)))):
            self.close()
            raise DocumentError('parser_unavailable', 503)

    def close(self):
        if self.handle:
            self.kernel.TerminateJobObject(self.handle, 1)
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class WorkerLock:
    """One local coordinator per storage root, including across API processes."""
    def __init__(self, root):
        self.file = (Path(root) / 'coordinator.lock').open('a+b')
        try:
            self.file.seek(0)
            if not self.file.read(1):
                self.file.write(b'0'); self.file.flush()
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise ValueError('资料目录已有解析服务，请使用单worker或独立数据目录') from None

    def close(self):
        if not self.file.closed:
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_UN)
            self.file.close()


def run_worker(manifest, output, cancel=None, timeout=60):
    """Only this module starts a parser process; no shell/credentials inherited."""
    import json
    env = {key: value for key, value in os.environ.items() if key in (
        'SYSTEMROOT', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'PATH')}
    env.update(PYTHONIOENCODING='utf-8', PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    process, job = None, None
    try:
        process = subprocess.Popen([sys.executable, '-m', 'eduagent.documents.worker', str(manifest), str(output)],
                                   stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   env=env, creationflags=0x08000000 if os.name == 'nt' else 0)
        if os.name == 'nt':
            job = WindowsJob(process)
        # Worker blocks on stdin until the parent's Job Object is configured.
        process.stdin.write(b'start\n'); process.stdin.flush(); process.stdin.close()
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if cancel is not None and cancel.is_set():
                raise DocumentError('parse_interrupted', 503)
            if time.monotonic() >= deadline:
                raise DocumentError('parse_timeout', 503)
            if output.exists() and output.stat().st_size > MAX_OUTPUT:
                raise DocumentError('document_too_large', 413)
            time.sleep(0.025)
        if not output.is_file() or output.stat().st_size > MAX_OUTPUT:
            raise DocumentError('parse_resource_limit', 503)
        payload = json.loads(output.read_text(encoding='utf8'))
        if payload.get('error'):
            raise DocumentError(payload['error'], 422)
        if process.returncode != 0:
            raise DocumentError('parse_failed', 503)
        return payload
    except DocumentError:
        raise
    except (OSError, ValueError, KeyError, BrokenPipeError):
        raise DocumentError('parse_failed', 503) from None
    finally:
        if job:
            job.close()
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)

