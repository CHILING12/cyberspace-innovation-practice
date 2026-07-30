from __future__ import annotations

import ctypes
import json
from ctypes import wintypes


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.GetSystemCpuSetInformation.argtypes = [
    ctypes.c_void_p,
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
    wintypes.HANDLE,
    wintypes.ULONG,
]
kernel32.GetSystemCpuSetInformation.restype = wintypes.BOOL

needed = wintypes.ULONG()
kernel32.GetSystemCpuSetInformation(
    None, 0, ctypes.byref(needed), kernel32.GetCurrentProcess(), 0
)
if not needed.value:
    raise ctypes.WinError(ctypes.get_last_error())

buffer = ctypes.create_string_buffer(needed.value)
if not kernel32.GetSystemCpuSetInformation(
    buffer,
    needed.value,
    ctypes.byref(needed),
    kernel32.GetCurrentProcess(),
    0,
):
    raise ctypes.WinError(ctypes.get_last_error())

raw = buffer.raw
offset = 0
rows = []
while offset < len(raw):
    size = int.from_bytes(raw[offset : offset + 4], "little")
    info_type = int.from_bytes(raw[offset + 4 : offset + 8], "little")
    if size <= 0:
        break
    if info_type == 0:
        rows.append(
            {
                "id": int.from_bytes(raw[offset + 8 : offset + 12], "little"),
                "group": int.from_bytes(raw[offset + 12 : offset + 14], "little"),
                "logical_processor_index": raw[offset + 14],
                "core_index": raw[offset + 15],
                "last_level_cache_index": raw[offset + 16],
                "numa_node_index": raw[offset + 17],
                "efficiency_class": raw[offset + 18],
                "flags": raw[offset + 19],
            }
        )
    offset += size

print(json.dumps(rows, indent=2))
