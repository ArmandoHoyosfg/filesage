from pathlib import Path

from filesage.core.config import Settings
from filesage.infrastructure.hash_cache import HashCache
from filesage.infrastructure.hasher import Hasher


def test_hash_cache_hit(tmp_path: Path):
    db = tmp_path / "c.db"
    cache = HashCache(db)
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello-world" * 100)
    st = f.stat()
    cache.put(
        f, size=st.st_size, mtime=st.st_mtime, kind="full", algo="xxhash64", digest="abc"
    )
    assert (
        cache.get(f, size=st.st_size, mtime=st.st_mtime, kind="full", algo="xxhash64")
        == "abc"
    )
    assert (
        cache.get(f, size=st.st_size + 1, mtime=st.st_mtime, kind="full", algo="xxhash64")
        is None
    )


def test_hasher_uses_cache(tmp_path: Path):
    settings = Settings()
    settings.hashing.use_cache = True
    settings.storage.index_db = str(tmp_path / "index.db")
    h = Hasher(settings)
    f = tmp_path / "x.bin"
    f.write_bytes(b"Z" * 50_000)
    d1 = h.full_hash(f)
    d2 = h.full_hash(f)
    assert d1 == d2
    f.write_bytes(b"Y" * 50_001)
    d3 = h.full_hash(f)
    assert d3 != d1
