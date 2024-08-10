"""
    Basic tester
"""

from typing import Optional, Coroutine, Any
from random import randint, choice
import logging
import asyncio
import time

from stub import MetaModule
import stub


async def time_coroutine(coroutine: Coroutine) -> tuple[float, Any]:
    st: float = time.time()
    resp: Any = await coroutine
    return (time.time() - st, resp)


async def routine(
    self: MetaModule,
    iterations: int,
    voice_id: int,
    log_id: int
) -> float:
    start: float = time.time()
    ctx: dict[str, Any] = {
        'voice_id': voice_id,
        'log_id': log_id,
        'logging': bool(randint(0, 1)),
        'lang_code': choice(['en', 'es', 'ch', 'gh']),
        'status_id': randint(0, 2 << 32)
    }

    context: 'stub.Context' = await self.ctx_new(**ctx)
    assert context.voice_id == ctx['voice_id']
    assert context.log_id == ctx['log_id']
    assert context.logging == ctx['logging']
    assert context.lang_code == ctx['lang_code']
    assert context.status_id == ctx['status_id']

    for _ in range(0, iterations):
        context.lang_code = choice(['en', 'es', 'ch', 'gh'])
        context.status_id = randint(0, 2 << 32)
        context.logging = bool(randint(0, 1))

        for k in ctx.keys():
            ctx[k] = getattr(context, k)

        context = await self.ctx_upd(context)
        assert context.voice_id == ctx['voice_id']
        assert context.log_id == ctx['log_id']
        assert context.logging == ctx['logging']
        assert context.lang_code == ctx['lang_code']
        assert context.status_id == ctx['status_id']
    
    await self.ctx_delete(context)
    # TODO: Assert
    return time.time() - start


async def test_post_install(self: MetaModule) -> Optional[Exception]:
    """
    Called after post_install

    Arguments
    ---------
    self
        The module to be tested
    
    Returns
    -------
    Exception, optional
        None if everything went well, in the other case
        it must return an exception
    """

    mod: MetaModule = await self.test_helper('Context')
    if not mod:
        return

    size: int = randint(10, 100)
    logging.debug('Simulating %d `Context` objects', size)

    start: int = randint(1, 2 << 30)
    logst: int = randint(
        start + size, (start + size) + (2 << 30))

    langs: list[str] = [
        'es', 'en', 'gh', 'hi'
    ]

    statuses: list[int] = [
        randint(1, 2 << 32) for x in range(0, size)]

    results: dict[str, float] = {
        'ctx_new': 0,
        'ctx_upd': 0,
        'ctx_delete': 0,
        'ctx_get_by_aid': 0,
        'ctx_get_by_voice': 0,
        'ctx_get_by_logid': 0
    }

    rgen_contexts: list['stub.Context'] = []
    for x in range(0, size):
        perf: float
        ctx: 'stub.Context'

        perf, ctx = await time_coroutine(mod.ctx_new(
            start + x, bool((start + x) % 2),
            logst + x, langs[(start + x) % len(langs)],
            statuses[x]
        ))

        results['ctx_new'] += perf
        assert ctx.voice_id == start + x
        assert ctx.logging == bool((start + x) % 2)
        assert ctx.log_id == logst + x
        assert ctx.lang_code == langs[(start + x) % len(langs)]
        assert ctx.status_id == statuses[x]

        rgen_contexts.append(ctx)

    for x in rgen_contexts:
        perf: float
        ctx: 'stub.Context'

        perf, ctx = await time_coroutine(mod.ctx_get_by_voice(x.voice_id))
        assert ctx == x
        results['ctx_get_by_voice'] += perf

        perf, ctx = await time_coroutine(mod.ctx_get_by_logid(x.log_id))
        assert ctx == x
        results['ctx_get_by_logid'] += perf

        perf, ctx = await time_coroutine(mod.ctx_get_by_aid(x.voice_id))
        assert ctx == x
        results['ctx_get_by_aid'] += perf

        perf, ctx = await time_coroutine(mod.ctx_get_by_aid(x.log_id))
        assert ctx == x
        results['ctx_get_by_aid'] += perf

        octx: 'stub.Context' = self.Context(**ctx.__dict__)
        for _ in range(0, 2):
            ctx.logging = not ctx.logging
            ctx.log_id = (1 << 63) - ctx.log_id
            ctx.lang_code = langs[len(langs) - langs.index(ctx.lang_code) - 1]
            ctx.status_id = (1 << 63) - ctx.status_id

            perf, nctx = await time_coroutine(mod.ctx_upd(ctx))
            assert nctx == ctx

            results['ctx_upd'] += perf

        assert octx == ctx
        perf, _ = await time_coroutine(mod.ctx_delete(x))
        results['ctx_delete'] += perf

        perf, ctx = await time_coroutine(mod.ctx_get_by_voice(x.voice_id))
        assert ctx is None
        results['ctx_get_by_voice'] += perf

    results['ctx_upd'] /= 2
    results['ctx_get_by_aid'] /= 2
    results['ctx_get_by_voice'] /= 2

    for k, v in results.items():
        logging.debug(
            'Results `%s`: %fms', k, (v / size) * 1000)

    tasks: int = 8
    runtime: float = 1
    separation: int = randint(1, 2 << 32)
    iterations: int = int(runtime / (
        (results['ctx_upd'] / size)
    ))

    logging.info(
        'Performing concurrency test for `%lf seconds`, '
        'with `%d tasks` and `%d iterations` (different ids)',
        runtime, tasks, iterations)

    futures: list[asyncio.Task] = []
    for x in range(0, tasks):
        futures.append(asyncio.create_task(routine(
            mod, iterations,
            (x + 1) * separation,
            (separation * (1 + tasks)) * (x + 1)
        )))

    await asyncio.sleep(runtime)

    elapsed: float = 0
    for fut in futures:
        elapsed += await fut
    elapsed /= tasks

    logging.info(
        'Concurrency test ran in `%lf seconds` correctly! '
        '(accuracy: %lf%%)', elapsed, runtime / elapsed * 100)


test_module: str = 'UStorage'
steps: dict[str, Optional[callable]] = {
    'post_install': test_post_install
}
