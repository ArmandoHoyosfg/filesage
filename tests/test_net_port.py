import socket

from filesage.utils.net import find_free_port, is_port_free


def test_find_free_port_returns_usable():
    host = "127.0.0.1"
    port = find_free_port(host, preferred=8765)
    assert 1 <= port <= 65535
    assert is_port_free(host, port)


def test_preferred_taken_falls_back():
    host = "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, 0))
    s.listen(1)
    busy = s.getsockname()[1]
    try:
        assert not is_port_free(host, busy)
        chosen = find_free_port(host, preferred=busy)
        assert chosen != busy
        assert is_port_free(host, chosen)
    finally:
        s.close()
