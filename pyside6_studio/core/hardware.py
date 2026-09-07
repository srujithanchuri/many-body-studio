"""Hardware detection and diagnostics for CUDA GPU and CPU fallback."""

import os
import sys

def get_hardware_info():
    """
    Detects active compute hardware (NVIDIA GPU via CuPy or CPU fallback).
    Returns a dict with:
      - 'backend': 'cuda' or 'cpu'
      - 'name': str (e.g. 'NVIDIA GeForce RTX 5060 Laptop GPU')
      - 'total_vram_gb': float or None
      - 'badge_text': str for UI display
      - 'is_gpu': bool
    """
    info = {
        "backend": "cpu",
        "name": "CPU Fallback (NumPy / SciPy)",
        "total_vram_gb": None,
        "badge_text": "💻 CPU Mode Active (Multithreaded)",
        "is_gpu": False
    }

    # Attempt to detect via CuPy
    try:
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount() > 0:
            dev_id = cp.cuda.runtime.getDevice()
            props = cp.cuda.runtime.getDeviceProperties(dev_id)
            name = props['name']
            if isinstance(name, bytes):
                name = name.decode('utf-8', errors='ignore')
            
            total_mem = props.get('totalGlobalMem', 0) / (1024 ** 3)
            info["backend"] = "cuda"
            info["name"] = name
            info["total_vram_gb"] = round(total_mem, 1)
            info["badge_text"] = f"⚡ GPU Active: {name} ({round(total_mem, 1)} GB VRAM)"
            info["is_gpu"] = True
            return info
    except Exception:
        pass

    # Fallback to CPU core count
    try:
        import multiprocessing
        cores = multiprocessing.cpu_count()
        info["name"] = f"Host CPU ({cores} logical cores)"
        info["badge_text"] = f"💻 CPU Active: {cores} Cores (CUDA Not Detected)"
    except Exception:
        pass

    return info
