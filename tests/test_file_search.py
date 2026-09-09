
from pathlib import Path

from filesage.services.file_search import match_file, rank_hits, APP_CONTEXT_DIRS


def test_name_match(tmp_path: Path):
    f = tmp_path / "report_converted.pdf"
    f.write_text("x")
    h = match_file(path=f, size=1, root=tmp_path, query="converted")
    assert h is not None
    assert h.match_why == "nombre"


def test_app_folder_does_not_match_without_name(tmp_path: Path):
    d = tmp_path / "FileSage_converted"
    d.mkdir()
    f = d / "photo.jpg"
    f.write_bytes(b"x")
    # sin use_path: no match
    assert match_file(path=f, size=1, root=tmp_path, query="converted") is None
    # con use_path: carpeta app no cuenta
    assert (
        match_file(path=f, size=1, root=tmp_path, query="converted", use_path=True)
        is None
    )


def test_meaningful_subfolder_path(tmp_path: Path):
    d = tmp_path / "proyectos" / "converted_backup"
    d.mkdir(parents=True)
    f = d / "a.txt"
    f.write_text("z")
    h = match_file(path=f, size=1, root=tmp_path, query="converted", use_path=True)
    assert h is not None
    assert "ruta" in h.match_why


def test_generic_meta_ignored(tmp_path: Path):
    f = tmp_path / "shot001.jpg"
    f.write_bytes(b"x")
    assert (
        match_file(
            path=f,
            size=1,
            root=tmp_path,
            query="jpeg",
            what="Imagen JPEG · 100x100",
            mime="image/jpeg",
            use_meta=True,
        )
        is None
    )


def test_specific_meta_match(tmp_path: Path):
    f = tmp_path / "shot001.jpg"
    f.write_bytes(b"x")
    h = match_file(
        path=f,
        size=1,
        root=tmp_path,
        query="ivanna",
        what="Retrato de Ivanna en estudio",
        mime="image/jpeg",
        use_meta=True,
    )
    assert h is not None
    assert "metadatos" in h.match_why
