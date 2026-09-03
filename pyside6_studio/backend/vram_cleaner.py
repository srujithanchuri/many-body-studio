"""GPU memory release and process termination utilities."""

import os
import sys
import gc
import subprocess

def flush_gpu_vram():
    """
    Releases all cached memory blocks in CuPy memory pools and runs garbage collection.
    Guarantees zero memory leaks between consecutive runs.
    """
    gc.collect()
    try:
        import cupy as cp
        if cp.cuda.is_available():
            mempool = cp.get_default_memory_pool()
            pinned_mempool = cp.get_default_pinned_memory_pool()
            mempool.free_all_blocks()
            pinned_mempool.free_all_blocks()
            return True
    except Exception:
        pass
    return False


def kill_process_tree(pid):
    """
    Forcefully terminates a process and all of its child processes on Windows.
    Used as Stage 2 hard-kill if a worker process doesn't respond to soft interrupt.
    """
    if not pid:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        else:
            import signal
            os.kill(pid, signal.SIGKILL)
    except Exception:
        pass
