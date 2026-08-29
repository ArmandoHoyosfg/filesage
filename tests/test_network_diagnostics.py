from filesage.services.network_diagnostics import (
    analyze,
    check_interfaces,
    check_tcp_latency,
    check_download_speed,
    run_full_diagnostics,
    CheckResult,
)


def test_interfaces_runs():
    c = check_interfaces()
    assert c.id == "interfaces"
    assert c.detail


def test_analyze_no_iface():
    checks = [
        CheckResult("interfaces", "Interfaces", False, "none", "error"),
    ]
    d = analyze(checks)
    assert d.confidence == "high"
    assert "enlace" in d.likely_cause.lower() or "IP" in d.likely_cause


def test_tcp_latency_smoke():
    c = check_tcp_latency(targets=(("1.1.1.1", 443),), samples=1)
    assert c.id == "latency"
    # puede fallar en sandbox sin red; solo estructura
    assert c.detail


def test_full_diagnostics_smoke():
    d = run_full_diagnostics(light_speed=True)
    assert d.checks
    assert d.likely_cause
    assert any(c.id == "latency" for c in d.checks)
    assert any(c.id == "speed" for c in d.checks)
