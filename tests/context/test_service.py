import asyncio
import multiprocessing
import time
import unittest

from backend.context.service import ContextBusy, ContextService, ContextUnavailable, run_child


def hanging_child(send, model, jpeg):
    time.sleep(30)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = []
        self.started = asyncio.Event()
        self.finish = asyncio.Event()
        async def runner(model, jpeg):
            if jpeg is None: return {'available': True}
            self.calls.append(jpeg)
            self.started.set()
            await self.finish.wait()
            return {'objects': ['chair'], 'uncertain': True}
        self.service = ContextService('gemini-fixture', runner=runner)
        await self.service.verify()
        self.addAsyncCleanup(self.service.close)

    async def test_one_active_one_pending_and_no_third_or_duplicate_session(self):
        a = self.service.reserve('a', {'a', 'b', 'c'})
        t1 = asyncio.create_task(self.service.describe(a, b'one'))
        await self.started.wait()
        b = self.service.reserve('b', {'a', 'b', 'c'})
        t2 = asyncio.create_task(self.service.describe(b, b'two'))
        await asyncio.sleep(.01)
        with self.assertRaises(ContextBusy): self.service.reserve('c', {'a', 'b', 'c'})
        with self.assertRaises(ContextBusy): self.service.reserve('a', {'a', 'b', 'c'})
        self.assertEqual(self.calls, [b'one'])
        self.finish.set()
        await asyncio.gather(t1, t2)
        self.assertEqual(self.calls, [b'one', b'two'])

    async def test_cooldown_replay_ids_and_session_cleanup_are_bounded(self):
        slot = self.service.reserve('a', {'a'})
        self.service.bind_id(slot, 'request-one')
        with self.assertRaises(ContextBusy): self.service.bind_id(slot, 'request-one')
        self.service.release(slot)
        with self.assertRaises(ContextBusy): self.service.reserve('a', {'a'})
        self.service.prune(set())
        self.assertEqual(self.service._ids, {})
        self.assertEqual(self.service._last, {})
        with self.assertRaises(ContextUnavailable): self.service.reserve('a', set())

    async def test_expiry_and_cancel_do_not_deliver_or_block_other_jobs(self):
        slot = self.service.reserve('a', {'a', 'b'})
        slot.deadline = asyncio.get_running_loop().time() + .02
        with self.assertRaises(ContextUnavailable):
            await self.service.describe(slot, b'expiring')
        self.service.release(slot)
        next_slot = self.service.reserve('b', {'a', 'b'})
        task = asyncio.create_task(self.service.describe(next_slot, b'cancelled'))
        await asyncio.sleep(.01)
        self.service.prune({'a'})
        with self.assertRaises(asyncio.CancelledError): await task

    async def test_unknown_model_never_reports_ready(self):
        async def fail(*args): raise RuntimeError('provider private error')
        service = ContextService('gemini-fixture', runner=fail)
        await service.verify()
        self.assertFalse(service.ready)
        with self.assertRaises(ContextUnavailable): service.reserve('a', {'a'})

    async def test_expired_pending_request_never_calls_provider(self):
        active = self.service.reserve('a', {'a', 'b'})
        active_task = asyncio.create_task(self.service.describe(active, b'active'))
        await self.started.wait()
        pending = self.service.reserve('b', {'a', 'b'})
        pending.deadline = asyncio.get_running_loop().time() + .02
        with self.assertRaises(ContextUnavailable):
            await self.service.describe(pending, b'pending')
        self.finish.set()
        await active_task
        self.assertEqual(self.calls, [b'active'])

    async def test_actual_spawned_hung_child_is_killed_on_deadline(self):
        before = {p.pid for p in multiprocessing.active_children()}
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            async with asyncio.timeout(.2):
                await run_child('gemini-fixture', b'fixture', target=hanging_child)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)


if __name__ == '__main__': unittest.main()
