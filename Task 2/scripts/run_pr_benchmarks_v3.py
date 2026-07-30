from __future__ import annotations

import ctypes
import os

import run_pr_benchmarks_v2 as base


def set_windows_execution_controls(cpu_index: int = 0) -> dict[str, object]:
    result: dict[str, object] = {
        "requested_cpu_index": cpu_index,
        "affinity_applied": False,
        "high_priority_applied": False,
    }
    if os.name != "nt":
        result["note"] = "Windows execution controls not applicable"
        return result
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel32.SetProcessAffinityMask.restype = ctypes.c_int
    kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.SetPriorityClass.restype = ctypes.c_int
    handle = kernel32.GetCurrentProcess()
    result["affinity_applied"] = bool(kernel32.SetProcessAffinityMask(handle, ctypes.c_size_t(1 << cpu_index)))
    result["affinity_error"] = ctypes.get_last_error()
    high_priority_class = 0x00000080
    result["high_priority_applied"] = bool(kernel32.SetPriorityClass(handle, high_priority_class))
    result["priority_error"] = ctypes.get_last_error()
    return result


if __name__ == "__main__":
    base.set_windows_execution_controls = set_windows_execution_controls
    base.main()
