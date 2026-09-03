"""CUDA environment and DLL auto-configuration for Many-Body Studio Pro.

Configures Windows DLL search paths and patches Numba CUDA paths to locate
NVIDIA CUDA Toolkit libraries (NVVM, libdevice, cudart) from pip wheel packages
(nvidia-cuda-nvcc-cu12, nvidia-cuda-runtime-cu12, etc.) seamlessly on Windows.
"""

import os
import sys
import glob
from collections import namedtuple

_INITIALIZED = False


def init_cuda_environment():
    """Initializes and verifies CUDA paths for Numba CUDA and CuPy."""
    global _INITIALIZED
    if _INITIALIZED:
        return True

    # 1. Discover site-packages and locate nvidia package directory
    candidate_dirs = []
    for p in sys.path:
        nv_dir = os.path.join(p, "nvidia")
        if os.path.isdir(nv_dir):
            candidate_dirs.append(nv_dir)

    # Also check virtualenv prefix
    venv_nv = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
    if os.path.isdir(venv_nv) and venv_nv not in candidate_dirs:
        candidate_dirs.append(venv_nv)

    if not candidate_dirs:
        _INITIALIZED = True
        return False

    nvidia_dir = candidate_dirs[0]

    # 2. Add all DLL directories to Windows DLL search path and PATH
    for root, dirs, files in os.walk(nvidia_dir):
        if any(f.lower().endswith(".dll") for f in files):
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(root)
                except Exception:
                    pass
            current_path = os.environ.get("PATH", "")
            if root not in current_path:
                os.environ["PATH"] = root + os.pathsep + current_path

    # 3. Locate specific critical CUDA compiler components
    nvvm_candidates = glob.glob(os.path.join(nvidia_dir, "**", "nvvm*.*"), recursive=True)
    nvvm_dll = next((p for p in nvvm_candidates if p.lower().endswith(".dll") and "nvvm" in os.path.basename(p).lower()), None)

    libdevice_candidates = glob.glob(os.path.join(nvidia_dir, "**", "libdevice*.*"), recursive=True)
    libdevice_bc = next((p for p in libdevice_candidates if p.lower().endswith(".bc")), None)

    cudart_candidates = glob.glob(os.path.join(nvidia_dir, "**", "cudart*.*"), recursive=True)
    cudart_dll = next((p for p in cudart_candidates if p.lower().endswith(".dll") and "cudart" in os.path.basename(p).lower()), None)

    nvcc_dir = os.path.join(nvidia_dir, "cuda_nvcc")
    if os.path.isdir(nvcc_dir):
        os.environ.setdefault("CUDA_HOME", nvcc_dir)
        os.environ.setdefault("CUDA_PATH", nvcc_dir)

    # 4. Configure Numba CUDA paths if Numba is installed
    try:
        import numba.cuda.cuda_paths as cp
        import numba.cuda.cudadrv.libs as libs

        EnvPath = namedtuple('_env_path_tuple', ['by', 'info'])
        runtime_bin = os.path.dirname(cudart_dll) if cudart_dll else None

        cached_paths = {
            'nvvm': EnvPath('pip_nvidia', nvvm_dll),
            'libdevice': EnvPath('pip_nvidia', libdevice_bc),
            'cudalib_dir': EnvPath('pip_nvidia', runtime_bin),
            'static_cudalib_dir': EnvPath('pip_nvidia', None),
        }
        cp.get_cuda_paths._cached_result = cached_paths

        orig_get_cudalib = libs.get_cudalib

        def patched_get_cudalib(lib, static=False):
            if lib == 'nvvm' and nvvm_dll:
                return nvvm_dll
            elif lib == 'cudart' and cudart_dll:
                return cudart_dll
            return orig_get_cudalib(lib, static=static)

        libs.get_cudalib = patched_get_cudalib
    except Exception:
        pass

    _INITIALIZED = True
    return True
