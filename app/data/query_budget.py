"""A process-wide warehouse gate retained until timed-out workers finish cleanup."""

import threading
from concurrent.futures import Future, TimeoutError


class QueryDeadlineExceeded(RuntimeError):
    pass


class QueryCapacityExceeded(RuntimeError):
    pass


_lock = threading.Lock()
_gates: dict[tuple[str, str], tuple[int, threading.BoundedSemaphore]] = {}


def execute_bounded(key, limit, queue_timeout, timeout, operation):
    with _lock:
        if key not in _gates:
            _gates[key] = (limit, threading.BoundedSemaphore(limit))
        configured, gate = _gates[key]
        if configured != limit:
            raise QueryCapacityExceeded("Inconsistent concurrency configuration for this warehouse")
    if not gate.acquire(timeout=queue_timeout):
        raise QueryCapacityExceeded("Warehouse query capacity exhausted")
    cancelled = threading.Event()
    cursor_lock = threading.Lock()
    holder = {}
    result = Future()

    def attach(cursor):
        with cursor_lock:
            holder["cursor"] = cursor
        if cancelled.is_set():
            raise QueryDeadlineExceeded("Query deadline expired before execution")

    def run():
        try:
            value = operation(cancelled, attach)
            result.set_result(value)
        except BaseException as error:
            result.set_exception(error)
        finally:
            # Never release capacity while a cancelled connector call is still alive.
            gate.release()

    def cancel():
        with cursor_lock:
            cursor = holder.get("cursor")
        if cursor is not None:
            try:
                cursor.cancel()
            except Exception:
                pass  # Server-side STATEMENT_TIMEOUT remains the backstop.

    threading.Thread(target=run, daemon=True).start()
    try:
        return result.result(timeout=timeout)
    except TimeoutError:
        cancelled.set()
        threading.Thread(target=cancel, daemon=True).start()
        raise QueryDeadlineExceeded(
            "Databricks query deadline exceeded; cancellation requested"
        ) from None
