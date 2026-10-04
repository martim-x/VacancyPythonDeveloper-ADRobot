"""Тесты ядра. Сеть замокана, сокеты не трогаем."""

import pytest

from app import core
from app.core import DownloadError, measure, stats

pytestmark = pytest.mark.unit

URL = "https://example.com/100MB.bin"
MB = 1_000_000


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.status_code = status
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def aiter_bytes(self, chunk):
        for i in range(0, len(self.body), chunk):
            yield self.body[i : i + chunk]


class FakeClient:
    """Отдаёт заготовленные ответы по кругу; Exception — вместо ответа."""

    def __init__(self, *results):
        self.results = list(results)
        self.count = 0

    def stream(self, method, url):
        self.count += 1
        result = self.results[min(self.count - 1, len(self.results) - 1)]
        if isinstance(result, Exception):
            raise result
        return result if isinstance(result, FakeResponse) else FakeResponse(result)


@pytest.mark.parametrize(
    "values, expected, std",
    [
        ([1.0, 2.0, 3.0, 4.0], 2.5, 1.2909944487358056),
        ([5.0] * 10, 5.0, 0.0),
        ([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0], 5.0, 2.138089935299395),
        ([7.3], 7.3, 0.0),
    ],
)
def test_stats(values, expected, std):
    assert stats(values)["expected"] == pytest.approx(expected)
    assert stats(values)["std"] == pytest.approx(std)


@pytest.mark.parametrize("count", [1, 3, 10])
async def test_makes_n_requests(count):
    report = await measure(URL, FakeClient(b"x" * 1000), requests=count, warmup=0)

    assert len(report["times"]) == count
    assert report["requests"] == count


async def test_default_is_ten_requests():
    assert (await measure(URL, FakeClient(b"x" * 100), warmup=0))["requests"] == 10


@pytest.mark.parametrize("warmup", [0, 1, 3])
async def test_warmup_not_in_results(warmup):
    client = FakeClient(b"x" * 1000)

    report = await measure(URL, client, requests=10, warmup=warmup)

    assert client.count == 10 + warmup
    assert len(report["times"]) == 10


@pytest.mark.parametrize("error", [DownloadError("HTTP 503"), DownloadError("ReadTimeout")])
async def test_failure_does_not_abort_run(error):
    client = FakeClient(b"x" * 1000, error, b"x" * 1000)

    report = await measure(URL, client, requests=3, warmup=0)

    assert len(report["times"]) == 2
    assert len(report["failures"]) == 1


async def test_all_failures_gives_no_stats():
    report = await measure(URL, FakeClient(DownloadError("timeout")), requests=5, warmup=0)

    assert report["times"] == []
    assert len(report["failures"]) == 5
    assert "average_mbps" not in report


async def test_totals_and_speed():
    report = await measure(URL, FakeClient(b"x" * (2 * MB), b"x" * MB), requests=2, warmup=0)

    assert sum(report["sizes"]) == 3 * MB
    assert report["total_mb"] == pytest.approx(3.0)
    assert report["average_mbps"] > 0
    assert report["speed"]["expected"] > 0


@pytest.mark.parametrize("status", [404, 500])
async def test_http_error_raises(status):
    with pytest.raises(DownloadError, match=f"HTTP {status}"):
        await core.download(URL, FakeClient(FakeResponse(b"", status)))


async def test_empty_body_raises():
    with pytest.raises(DownloadError, match="пустой"):
        await core.download(URL, FakeClient(b""))


async def test_download_returns_time_and_size():
    elapsed, size = await core.download(URL, FakeClient(b"x" * 5000))

    assert size == 5000
    assert elapsed > 0
