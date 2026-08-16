import pytest

from cata.errors import Blocked, NotFound, TransportError
from cata.fetch import Fetcher


class FakeResponse:
    def __init__(self, status_code, text="", url="https://www.catawiki.com/en/l/1"):
        self.status_code = status_code
        self.text = text
        self.url = url


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self.responses.pop(0)


def test_get_returns_body(tmp_path):
    session = FakeSession([FakeResponse(200, "<html>ok</html>")])
    f = Fetcher(cache_dir=tmp_path, rate_per_second=1000, session=session)
    assert f.get("https://www.catawiki.com/en/l/1") == "<html>ok</html>"


def test_get_caches_second_call(tmp_path):
    session = FakeSession([FakeResponse(200, "<html>ok</html>")])
    f = Fetcher(cache_dir=tmp_path, rate_per_second=1000, session=session)
    f.get("https://www.catawiki.com/en/l/1")
    assert f.get("https://www.catawiki.com/en/l/1") == "<html>ok</html>"
    assert len(session.calls) == 1


def test_repeated_403_raises_blocked(tmp_path):
    session = FakeSession([FakeResponse(403) for _ in range(4)])
    f = Fetcher(cache_dir=tmp_path, rate_per_second=1000, session=session, retries=3)
    with pytest.raises(Blocked):
        f.get("https://www.catawiki.com/en/l/1")


class ExplodingSession:
    def __init__(self, failures, then=None):
        self.failures = failures
        self.then = then
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise TimeoutError("Operation timed out")
        if self.then is None:
            raise TimeoutError("Operation timed out")
        return self.then


def test_transport_failure_is_retried_then_succeeds(tmp_path):
    session = ExplodingSession(2, then=FakeResponse(200, "<html>ok</html>"))
    f = Fetcher(cache_dir=tmp_path, rate_per_second=1000, session=session, retries=3)
    assert f.get("https://www.catawiki.com/en/l/1") == "<html>ok</html>"
    assert session.calls == 3


def test_persistent_transport_failure_raises_cata_error(tmp_path):
    session = ExplodingSession(99)
    f = Fetcher(cache_dir=tmp_path, rate_per_second=1000, session=session, retries=1)
    with pytest.raises(TransportError):
        f.get("https://www.catawiki.com/en/l/1")


def test_redirect_to_category_is_not_found(tmp_path):
    session = FakeSession(
        [FakeResponse(200, "<html></html>", url="https://www.catawiki.com/en/c/507-home")]
    )
    f = Fetcher(cache_dir=tmp_path, rate_per_second=1000, session=session)
    with pytest.raises(NotFound):
        f.get("https://www.catawiki.com/en/l/103000000")
