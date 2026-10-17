"""Single active Gemini child plus one pending job, separate from inference."""
import asyncio
from dataclasses import dataclass, field
import json
import multiprocessing

from .provider import child, validate_result


class ContextUnavailable(Exception):
    def __init__(self, http_status=None):
        self.http_status = http_status if type(http_status) is int and 400 <= http_status <= 599 else None
        super().__init__('Description unavailable')


class ContextBusy(Exception):
    pass


async def run_child(model, jpeg, *, target=child):
    ctx = multiprocessing.get_context('spawn')
    receive, send = ctx.Pipe(duplex=False)
    process = ctx.Process(target=target, args=(send, model, jpeg), daemon=True)
    try:
        process.start()
        send.close()
        while not receive.poll():
            if not process.is_alive():
                raise ContextUnavailable()
            await asyncio.sleep(.01)
        value = json.loads(receive.recv_bytes(4096))
        if type(value) is dict and value.get('unavailable') is True:
            raise ContextUnavailable(value.get('http_status'))
        if jpeg is None:
            if value != {'available': True}:
                raise ContextUnavailable()
            return value
        return validate_result(value)
    except (OSError, EOFError, ValueError, KeyError, TypeError):
        raise ContextUnavailable() from None
    finally:
        receive.close()
        send.close()
        if process.pid is not None:
            if process.is_alive():
                process.kill()
            process.join(timeout=.2)
            process.close()


@dataclass
class Slot:
    session_id: str
    deadline: float
    task: object = field(default=None, repr=False)


class ContextService:
    """One event loop only; no retry, durable queue, raw image or result cache."""
    def __init__(self, model, *, runner=run_child):
        self.model = model
        self.runner = runner
        self.ready = False
        self.verification_http_status = None
        self._closed = False
        self._slots = {}
        self._last = {}
        self._ids = {}
        self._active = asyncio.Semaphore(1)

    async def verify(self):
        try:
            async with asyncio.timeout(8):
                if await self.runner(self.model, None) != {'available': True}:
                    raise ContextUnavailable()
            self.ready = True
        except ContextUnavailable as error:
            self.ready = False
            self.verification_http_status = error.http_status
        except Exception:
            self.ready = False

    def reserve(self, session_id, valid_sessions):
        """Admission precedes body parsing. Limit storage to actual active pairs."""
        self.prune(valid_sessions)
        if self._closed or not self.ready or session_id not in valid_sessions:
            raise ContextUnavailable()
        now = asyncio.get_running_loop().time()
        if (len(self._slots) >= 2 or session_id in self._slots
                or now - self._last.get(session_id, float('-inf')) < 10):
            raise ContextBusy()
        if len(self._ids.get(session_id, set())) >= 32:
            raise ContextBusy()  # Reenroll instead of evicting replay history.
        self._last[session_id] = now
        slot = Slot(session_id, now + 8)
        self._slots[session_id] = slot
        return slot

    def bind_id(self, slot, request_id):
        ids = self._ids.setdefault(slot.session_id, set())
        if request_id in ids:
            raise ContextBusy()
        ids.add(request_id)

    async def describe(self, slot, jpeg):
        async def work():
            async with self._active:
                if asyncio.get_running_loop().time() >= slot.deadline:
                    raise ContextUnavailable()
                return validate_result(await self.runner(self.model, jpeg))
        try:
            if asyncio.get_running_loop().time() >= slot.deadline:
                raise ContextUnavailable()
            slot.task = asyncio.create_task(work())
            async with asyncio.timeout_at(slot.deadline):
                return await slot.task
        except Exception:
            raise ContextUnavailable() from None

    def release(self, slot):
        if slot.task is not None and not slot.task.done():
            slot.task.cancel()
        if self._slots.get(slot.session_id) is slot:
            self._slots.pop(slot.session_id)

    def prune(self, valid_sessions):
        for sid in list(self._slots):
            if sid not in valid_sessions:
                self.release(self._slots[sid])
        for mapping in (self._last, self._ids):
            for sid in list(mapping):
                if sid not in valid_sessions:
                    mapping.pop(sid)

    async def close(self):
        self._closed = True
        tasks = [slot.task for slot in self._slots.values() if slot.task is not None]
        for slot in list(self._slots.values()):
            self.release(slot)
        await asyncio.gather(*tasks, return_exceptions=True)
        self._last.clear()
        self._ids.clear()
