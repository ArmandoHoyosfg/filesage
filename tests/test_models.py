"""Tests básicos de los modelos de dominio."""

from pathlib import Path

from filesage.domain.models import FileInfo, DuplicateGroup, KeepStrategy


def test_fileinfo_creation():
    fi = FileInfo(
        path=Path("/tmp/test.txt"),
        size=1024,
        mtime=1700000000.0,
    )
    assert fi.path == Path("/tmp/test.txt")
    assert fi.size == 1024
    assert fi.extension == ".txt"
    assert fi.hash_full is None


def test_fileinfo_with_hashes():
    fi = FileInfo(path=Path("a.bin"), size=100, mtime=1.0)
    fi2 = fi.with_hashes(partial="abc", full="def")
    assert fi2.hash_partial == "abc"
    assert fi2.hash_full == "def"
    assert fi.hash_partial is None  # inmutabilidad


def test_duplicate_group():
    f1 = FileInfo(path=Path("a"), size=100, mtime=1.0)
    f2 = FileInfo(path=Path("b"), size=100, mtime=2.0)
    group = DuplicateGroup(
        hash_full="xyz",
        files=(f1, f2),
        total_size=200,
        wasted_size=100,
    )
    assert group.count == 2
    assert group.wasted_size == 100


def test_keep_strategy_enum():
    assert KeepStrategy.NEWEST.value == "newest"
