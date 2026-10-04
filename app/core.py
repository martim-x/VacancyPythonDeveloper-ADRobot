import time
from statistics import fmean, stdev

import httpx

MB = 1_000_000


class DownloadError(Exception):
    pass


async def download(url, client):
    started = time.perf_counter()
    size = 0
    try:
        async with client.stream("GET", url) as response:
            if response.status_code >= 400:
                raise DownloadError(f"HTTP {response.status_code}")
            async for chunk in response.aiter_bytes(64 * 1024):
                size += len(chunk)
    except httpx.HTTPError as exc:
        raise DownloadError(f"{type(exc).__name__}: {exc}") from exc
    if not size:
        raise DownloadError("пустой ответ")
    return time.perf_counter() - started, size


def stats(values):
    return {
        "expected": fmean(values),
        "std": stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


async def measure(url, client, requests=10, warmup=1, on_result=None):
    for _ in range(warmup):
        try:
            await download(url, client)
        except DownloadError:
            pass

    times, sizes, failures = [], [], []
    started = time.perf_counter()
    for number in range(1, requests + 1):
        try:
            elapsed, size = await download(url, client)
        except DownloadError as exc:
            failures.append((number, str(exc)))
            if on_result:
                on_result(number, None, exc)
            continue
        times.append(elapsed)
        sizes.append(size)
        if on_result:
            on_result(number, elapsed, size)
    wall = time.perf_counter() - started

    total = sum(sizes)
    report = {
        "url": url,
        "requests": requests,
        "times": times,
        "sizes": sizes,
        "failures": failures,
        "wall_time": wall,
        "total_mb": total / MB,
    }
    if times:
        report["average_mbps"] = (total / MB) / wall
        report["time"] = stats(times)
        report["speed"] = stats([(s / MB) / t for s, t in zip(sizes, times)])
    return report
