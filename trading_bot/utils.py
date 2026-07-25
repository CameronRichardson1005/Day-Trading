import time
from collections.abc import Callable
from typing import Any


def call_with_retries(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    backoff_seconds: int = 2,
    label: str = "request",
    **kwargs: Any,
) -> Any:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            result = func(*args, **kwargs)

            if hasattr(result, "raise_for_status"):
                result.raise_for_status()

            return result

        except Exception as error:
            last_error = error

            if attempt == max_retries:
                break

            wait_seconds = backoff_seconds * attempt

            print(
                f"{label} failed "
                f"(attempt {attempt}/{max_retries}): "
                f"{error}. Retrying in {wait_seconds} seconds."
            )

            time.sleep(wait_seconds)

    if last_error is None:
        raise RuntimeError(f"{label} failed without an error message.")

    raise last_error