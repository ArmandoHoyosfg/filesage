"""Contratos de session_store y helpers de UI (sin cliente NiceGUI)."""

from __future__ import annotations

import pytest

from filesage.presentation.web import session_store


@pytest.mark.integrity
def test_page_state_roundtrip():
    session_store.update_page_state(
        "/smart",
        plan=None,
        checks={"a": True},
        status="ok",
        folder_path="/tmp",
    )
    st = session_store.get_page_state("/smart")
    assert st.get("checks") == {"a": True}
    assert st.get("status") == "ok"
    assert "results" not in st or st.get("results") is None or isinstance(
        st.get("results"), (list, type(None))
    )


@pytest.mark.integrity
def test_search_state_has_results_key_isolation():
    session_store.update_page_state("/search", results=[{"path": "/x"}], checks={})
    session_store.update_page_state("/smart", plan=None, checks={})
    smart = session_store.get_page_state("/smart")
    search = session_store.get_page_state("/search")
    assert "results" not in smart or smart.get("results") is None
    assert search.get("results")


@pytest.mark.integrity
def test_selection_bag():
    if not hasattr(session_store, "set_selection"):
        pytest.skip("sin selection bag")
    session_store.set_selection(
        ["/a", "/b"], source="search", label="test"
    )
    # get si existe
    getter = getattr(session_store, "get_selection", None)
    if getter:
        sel = getter()
        assert sel is not None
