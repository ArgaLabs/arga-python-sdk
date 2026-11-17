from urllib.parse import quote


def segment(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier or identifier in {".", ".."}:
        raise ValueError("Supply a nonempty resource identifier")
    return quote(identifier, safe="")


def artifact_path(filename: str) -> str:
    if (
        not filename
        or filename.startswith("/")
        or "\\" in filename
        or any(part in {".", ".."} for part in filename.split("/"))
    ):
        raise ValueError("Supply an artifact path within the run")
    return quote(filename, safe="/")


def polling_bounds(poll_interval: float, timeout: float) -> None:
    import math

    if not math.isfinite(poll_interval) or not math.isfinite(timeout) or poll_interval <= 0 or timeout <= 0:
        raise ValueError("Polling interval and timeout must be finite and positive")
