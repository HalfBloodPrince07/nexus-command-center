import logging

try:
    import psutil
except ImportError:  # pragma: no cover - optional runtime dependency
    psutil = None
    logging.getLogger(__name__).warning("psutil not available - system metrics will be degraded.")

logger = logging.getLogger(__name__)

# Try importing GPUtil for NVIDIA GPU metrics
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    logger.info("GPUtil not available — GPU metrics will be disabled.")


def get_system_metrics() -> dict:
    """Collect current system metrics: CPU, RAM, and GPU (if NVIDIA available)."""
    if psutil is None:
        return {
            "cpu_percent": None,
            "ram_percent": None,
            "ram_used_gb": None,
            "ram_total_gb": None,
            "gpu_percent": None,
            "gpu_temp_c": None,
            "gpu_vram_percent": None,
            "gpu_name": None,
        }

    # CPU — non-blocking (returns value since last call)
    cpu_percent = psutil.cpu_percent(interval=None)

    # RAM
    ram = psutil.virtual_memory()
    ram_percent = ram.percent
    ram_used_gb = round(ram.used / (1024 ** 3), 1)
    ram_total_gb = round(ram.total / (1024 ** 3), 1)

    metrics = {
        "cpu_percent": cpu_percent,
        "ram_percent": ram_percent,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "gpu_percent": None,
        "gpu_temp_c": None,
        "gpu_vram_percent": None,
        "gpu_name": None,
    }

    # GPU (NVIDIA)
    if GPU_AVAILABLE:
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # primary GPU
                metrics["gpu_percent"] = round(gpu.load * 100, 1)
                metrics["gpu_temp_c"] = gpu.temperature
                metrics["gpu_vram_percent"] = round(gpu.memoryUtil * 100, 1) if gpu.memoryUtil else 0.0
                metrics["gpu_name"] = gpu.name
        except Exception as e:
            logger.debug("Failed to read GPU metrics: %s", e)

    return metrics


if psutil is not None:
    # Prime the CPU percent counter on import so the first real call returns meaningful data
    psutil.cpu_percent(interval=None)
