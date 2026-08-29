from filesage.services.network_diagnostics import (
    analyze,
    check_interfaces,
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


def test_full_diagnostics_smoke():
    d = run_full_diagnostics()
    assert d.checks
    assert d.likely_cause
    assert d.confidence in ("high", "medium", "low")
