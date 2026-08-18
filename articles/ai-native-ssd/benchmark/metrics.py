"""Shared metrics contract for every experiment in this benchmark family.

Every run, in every experiment, emits the same core triple so results stay
comparable across experiments and articles:

    storage_bytes_read   bytes the owning process pulled off the drive
    boundary_bytes       bytes that crossed the host<->device boundary
                         (down + up; for host-side methods this equals
                         storage_bytes_read, because the host IS across
                         the boundary from the drive)
    useful_bytes         bytes of the answer the caller actually wanted

plus wall time and per-process CPU seconds. Extra per-experiment fields go
in "extras". One JSON object per line, appended to a .jsonl file.
"""
import json
import os
import time


def make_run(experiment: str, config: dict, storage_bytes_read: int,
             boundary_down: int, boundary_up: int, useful_bytes: int,
             wall_s: float, host_cpu_s: float = None, device_cpu_s: float = None,
             extras: dict = None) -> dict:
    boundary = boundary_down + boundary_up
    run = {
        "experiment": experiment,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": config,
        "storage_bytes_read": storage_bytes_read,
        "boundary_bytes_down": boundary_down,
        "boundary_bytes_up": boundary_up,
        "boundary_bytes": boundary,
        "useful_bytes": useful_bytes,
        "boundary_waste_ratio": round(boundary / useful_bytes, 1) if useful_bytes else None,
        "storage_waste_ratio": round(storage_bytes_read / useful_bytes, 1) if useful_bytes else None,
        "wall_s": round(wall_s, 4),
    }
    if host_cpu_s is not None:
        run["host_cpu_s"] = round(host_cpu_s, 3)
    if device_cpu_s is not None:
        run["device_cpu_s"] = round(device_cpu_s, 3)
    if extras:
        run["extras"] = extras
    return run


def emit(path: str, run: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(run) + "\n")


def load(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
