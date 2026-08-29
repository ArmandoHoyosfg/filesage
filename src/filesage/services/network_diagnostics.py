"""Diagnostico inteligente de red y reparaciones seguras.

Capas:
1. Interfaces / gateway / DNS del sistema
2. Resolucion DNS (stdlib + dnspython si esta)
3. Alcance ICMP (icmplib o ping del SO)
4. HTTP/HTTPS saliente
5. Heuristica de causa mas probable + acciones sugeridas

Las reparaciones destructivas (Winsock, etc.) exigen confirmacion explicita
y privilegios de administrador; no se ejecutan solas.
"""

from __future__ import annotations

import json
import logging
import platform
import socket
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

PUBLIC_DNS = ("1.1.1.1", "8.8.8.8", "9.9.9.9")
TEST_HOSTS = ("cloudflare.com", "google.com", "microsoft.com")
HTTP_URLS = (
    "https://www.cloudflare.com/cdn-cgi/trace",
    "http://connectivitycheck.gstatic.com/generate_204",
)


@dataclass
class CheckResult:
    id: str
    title: str
    ok: bool
    detail: str
    severity: str = "info"  # info | warn | error
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Diagnosis:
    checks: list[CheckResult]
    likely_cause: str
    confidence: str  # high | medium | low
    recommendations: list[str]
    suggested_repairs: list[str]  # ids seguros


@dataclass
class RepairResult:
    id: str
    ok: bool
    message: str


def _run_cmd(args: list[str], timeout: float = 12) -> tuple[int, str]:
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            **(
                {"creationflags": subprocess.CREATE_NO_WINDOW}
                if platform.system() == "Windows" and hasattr(subprocess, "CREATE_NO_WINDOW")
                else {}
            ),
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except Exception as e:
        return 1, str(e)


def check_interfaces() -> CheckResult:
    hostname = socket.gethostname()
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    # fallback: UDP trick for default route IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("1.1.1.1", 80))
        local = s.getsockname()[0]
        s.close()
        if local not in ips:
            ips.insert(0, local)
    except Exception:
        pass

    if not ips:
        return CheckResult(
            "interfaces",
            "Interfaces / IP local",
            False,
            "No se detecto IP local util (posible desconexion total).",
            "error",
        )
    return CheckResult(
        "interfaces",
        "Interfaces / IP local",
        True,
        f"Host {hostname} · IP(s): {', '.join(ips[:6])}",
        "info",
        {"hostname": hostname, "ips": ips},
    )


def check_dns_resolve(host: str = "cloudflare.com") -> CheckResult:
    t0 = time.perf_counter()
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addrs = sorted({i[4][0] for i in infos})
        ms = (time.perf_counter() - t0) * 1000
        detail = f"{host} → {', '.join(addrs[:4])} ({ms:.0f} ms)"
        extra: dict[str, Any] = {"host": host, "addrs": addrs, "ms": ms}

        # dnspython: mas detalle
        try:
            import dns.resolver  # type: ignore

            ans = dns.resolver.resolve(host, "A")
            extra["dnspython_a"] = [r.to_text() for r in ans]
        except Exception as e:
            extra["dnspython"] = f"no disponible o error: {e}"

        return CheckResult("dns", "Resolucion DNS", True, detail, "info", extra)
    except socket.gaierror as e:
        return CheckResult(
            "dns",
            "Resolucion DNS",
            False,
            f"Fallo resolviendo {host}: {e}",
            "error",
            {"host": host, "error": str(e)},
        )
    except Exception as e:
        return CheckResult("dns", "Resolucion DNS", False, str(e), "error")


def check_dns_servers() -> CheckResult:
    """Consulta A a resolvers publicos (si dnspython) o getaddrinfo."""
    results: dict[str, str] = {}
    ok_any = False
    try:
        import dns.resolver  # type: ignore

        for server in PUBLIC_DNS:
            try:
                r = dns.resolver.Resolver(configure=False)
                r.nameservers = [server]
                r.lifetime = 3
                ans = r.resolve("example.com", "A")
                results[server] = ", ".join(x.to_text() for x in ans)
                ok_any = True
            except Exception as e:
                results[server] = f"FAIL: {e}"
    except ImportError:
        # sin dnspython: solo sistema
        c = check_dns_resolve("example.com")
        return CheckResult(
            "dns_public",
            "DNS publicos",
            c.ok,
            "Instala dnspython para probar 1.1.1.1 / 8.8.8.8. " + c.detail,
            c.severity if not c.ok else "info",
        )

    detail = " · ".join(f"{k}: {v}" for k, v in results.items())
    return CheckResult(
        "dns_public",
        "DNS publicos (1.1.1.1 / 8.8.8.8)",
        ok_any,
        detail[:400],
        "info" if ok_any else "error",
        results,
    )


def check_ping(target: str = "1.1.1.1", count: int = 3) -> CheckResult:
    # icmplib primero
    try:
        from icmplib import ping  # type: ignore

        host = ping(target, count=count, interval=0.3, timeout=2, privileged=False)
        ok = host.is_alive
        detail = (
            f"{target}: {'OK' if ok else 'sin respuesta'} · "
            f"avg {host.avg_rtt:.1f} ms · loss {host.packet_loss*100:.0f}%"
        )
        return CheckResult(
            "ping",
            f"Ping {target}",
            ok,
            detail,
            "info" if ok else "warn",
            {
                "avg_rtt": host.avg_rtt,
                "packet_loss": host.packet_loss,
                "engine": "icmplib",
            },
        )
    except Exception as e:
        logger.debug("icmplib ping fallo: %s", e)

    # fallback SO
    system = platform.system()
    if system == "Windows":
        code, out = _run_cmd(["ping", "-n", str(count), "-w", "2000", target])
    else:
        code, out = _run_cmd(["ping", "-c", str(count), "-W", "2", target])
    ok = code == 0
    line = out.splitlines()[-1] if out else ""
    return CheckResult(
        "ping",
        f"Ping {target}",
        ok,
        (line or out or "sin salida")[:300],
        "info" if ok else "warn",
        {"engine": "system_ping", "code": code},
    )


def check_http(url: str = HTTP_URLS[0]) -> CheckResult:
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "FileSage/0.8"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            code = getattr(resp, "status", 200)
            ms = (time.perf_counter() - t0) * 1000
            ok = 200 <= int(code) < 400 or int(code) == 204
            return CheckResult(
                "http",
                "Salida HTTP/HTTPS",
                ok,
                f"{url} → {code} ({ms:.0f} ms)",
                "info" if ok else "warn",
                {"url": url, "status": code, "ms": ms},
            )
    except urllib.error.URLError as e:
        return CheckResult(
            "http",
            "Salida HTTP/HTTPS",
            False,
            f"Fallo {url}: {e.reason}",
            "error",
            {"url": url, "error": str(e)},
        )
    except Exception as e:
        return CheckResult("http", "Salida HTTP/HTTPS", False, str(e), "error")


def check_gateway() -> CheckResult:
    system = platform.system()
    if system == "Windows":
        code, out = _run_cmd(["route", "print", "0.0.0.0"])
        gw = None
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "0.0.0.0":
                gw = parts[2]
                break
        if gw and gw != "On-link":
            return CheckResult(
                "gateway",
                "Puerta de enlace",
                True,
                f"Default gateway: {gw}",
                "info",
                {"gateway": gw},
            )
        return CheckResult(
            "gateway",
            "Puerta de enlace",
            False,
            "No se detecto gateway por defecto.",
            "error",
            {"raw": out[:200]},
        )
    # Linux / macOS
    if system == "Darwin":
        code, out = _run_cmd(["route", "-n", "get", "default"])
        gw = None
        for line in out.splitlines():
            if "gateway:" in line.lower():
                gw = line.split(":")[-1].strip()
        ok = bool(gw)
        return CheckResult(
            "gateway",
            "Puerta de enlace",
            ok,
            f"gateway: {gw}" if gw else out[:200],
            "info" if ok else "error",
            {"gateway": gw},
        )
    code, out = _run_cmd(["ip", "route", "show", "default"])
    if code != 0:
        code, out = _run_cmd(["route", "-n"])
    ok = "default" in out or "0.0.0.0" in out
    return CheckResult(
        "gateway",
        "Puerta de enlace",
        ok,
        out[:250] or "sin ruta por defecto",
        "info" if ok else "error",
    )


def analyze(checks: list[CheckResult]) -> Diagnosis:
    by_id = {c.id: c for c in checks}
    recs: list[str] = []
    repairs: list[str] = []

    iface = by_id.get("interfaces")
    gw = by_id.get("gateway")
    dns = by_id.get("dns")
    dns_pub = by_id.get("dns_public")
    ping = by_id.get("ping")
    http = by_id.get("http")

    # Heuristica
    if iface and not iface.ok:
        return Diagnosis(
            checks,
            "Sin conectividad de enlace/IP local. Cable, Wi‑Fi desconectado o adaptador deshabilitado.",
            "high",
            [
                "Comprueba Wi‑Fi/cable y que el adaptador este activado.",
                "Reinicia el router si otros dispositivos tampoco tienen red.",
            ],
            [],
        )

    if gw and not gw.ok:
        return Diagnosis(
            checks,
            "No hay puerta de enlace por defecto (DHCP fallido o red mal configurada).",
            "high",
            [
                "Renueva la IP (DHCP).",
                "Revisa que el router este encendido.",
            ],
            ["renew_dhcp"],
        )

    if dns and not dns.ok and ping and ping.ok:
        return Diagnosis(
            checks,
            "La red responde (ping) pero falla el DNS del sistema.",
            "high",
            [
                "Prueba DNS publicos (1.1.1.1 / 8.8.8.8).",
                "Vaciar la cache DNS suele ayudar.",
            ],
            ["flush_dns"],
        )

    if dns and not dns.ok and (not ping or not ping.ok):
        return Diagnosis(
            checks,
            "Sin resolucion DNS y sin respuesta ICMP a Internet: posible corte de red o firewall.",
            "medium",
            [
                "Verifica el router y el estado del ISP.",
                "Desactiva temporalmente VPN/proxy si los usas.",
            ],
            ["flush_dns", "renew_dhcp"],
        )

    if ping and not ping.ok and http and http.ok:
        return Diagnosis(
            checks,
            "ICMP bloqueado (comun en redes corporativas); HTTP funciona: la red util esta OK.",
            "high",
            ["No es un fallo grave si navegas con normalidad."],
            [],
        )

    if http and not http.ok and dns and dns.ok:
        return Diagnosis(
            checks,
            "DNS OK pero no hay salida HTTP/HTTPS (proxy, firewall o filtrado).",
            "medium",
            [
                "Revisa proxy del sistema y firewall.",
                "Prueba otro puerto/red (p. ej. datos moviles).",
            ],
            [],
        )

    if all(c.ok for c in checks if c.id in ("interfaces", "dns", "http")):
        return Diagnosis(
            checks,
            "No se detectan fallos graves de conectividad basica.",
            "high",
            ["La red parece operativa. Si una app falla, el problema puede ser de esa app o del servidor remoto."],
            [],
        )

    # generico
    failed = [c.title for c in checks if not c.ok]
    return Diagnosis(
        checks,
        "Problema mixto: fallan → " + (", ".join(failed) if failed else "varios checks"),
        "low",
        [
            "Revisa los checks en rojo/amarillo.",
            "Vaciar DNS y renovar DHCP son primeros pasos seguros.",
        ],
        ["flush_dns"],
    )


def run_full_diagnostics(*, progress=None) -> Diagnosis:
    steps = [
        ("Interfaces", check_interfaces),
        ("Gateway", check_gateway),
        ("DNS sistema", check_dns_resolve),
        ("DNS publicos", check_dns_servers),
        ("Ping", lambda: check_ping("1.1.1.1")),
        ("HTTP", check_http),
    ]
    checks: list[CheckResult] = []
    n = len(steps)
    for i, (label, fn) in enumerate(steps):
        if progress:
            progress.report(f"Comprobando: {label}…", (i + 0.2) / n)
        try:
            checks.append(fn())
        except Exception as e:
            checks.append(
                CheckResult(label.lower(), label, False, str(e), "error")
            )
        if progress:
            progress.report(f"Listo: {label}", (i + 1) / n)
    return analyze(checks)


def repair_flush_dns() -> RepairResult:
    system = platform.system()
    if system == "Windows":
        code, out = _run_cmd(["ipconfig", "/flushdns"])
        ok = code == 0
        return RepairResult("flush_dns", ok, out or ("OK" if ok else "Fallo"))
    if system == "Darwin":
        code, out = _run_cmd(["dscacheutil", "-flushcache"])
        _run_cmd(["killall", "-HUP", "mDNSResponder"])
        return RepairResult("flush_dns", True, "Cache DNS macOS vaciada (mejor esfuerzo)")
    # Linux
    for cmd in (
        ["resolvectl", "flush-caches"],
        ["systemd-resolve", "--flush-caches"],
        ["nscd", "-i", "hosts"],
    ):
        code, out = _run_cmd(cmd)
        if code == 0:
            return RepairResult("flush_dns", True, f"OK via {cmd[0]}: {out or 'vaciado'}")
    return RepairResult(
        "flush_dns",
        False,
        "No se encontro comando de flush DNS en este Linux (resolvectl/nscd).",
    )


def repair_renew_dhcp() -> RepairResult:
    system = platform.system()
    if system == "Windows":
        c1, o1 = _run_cmd(["ipconfig", "/release"])
        c2, o2 = _run_cmd(["ipconfig", "/renew"])
        ok = c2 == 0
        return RepairResult("renew_dhcp", ok, (o1 + "\n" + o2).strip()[:500])
    if system == "Darwin":
        return RepairResult(
            "renew_dhcp",
            False,
            "En macOS renueva DHCP desde Ajustes de red o: sudo ipconfig set en0 DHCP",
        )
    code, out = _run_cmd(["nmcli", "networking", "off"])
    _run_cmd(["nmcli", "networking", "on"])
    if code == 0:
        return RepairResult("renew_dhcp", True, "nmcli networking off/on")
    return RepairResult(
        "renew_dhcp",
        False,
        "Renovar DHCP requiere NetworkManager (nmcli) o privilegios (dhclient).",
    )


def repair_winsock_reset() -> RepairResult:
    """Windows: netsh winsock reset — requiere admin y reinicio. Irreversible hasta reiniciar."""
    if platform.system() != "Windows":
        return RepairResult("winsock_reset", False, "Solo aplica a Windows")
    code, out = _run_cmd(["netsh", "winsock", "reset"])
    ok = code == 0
    msg = (out or "")[:400]
    if ok:
        msg += " · Reinicia el PC para aplicar."
    else:
        msg += " · Ejecuta FileSage como administrador si fallo por permisos."
    return RepairResult("winsock_reset", ok, msg)


REPAIR_FUNCS = {
    "flush_dns": repair_flush_dns,
    "renew_dhcp": repair_renew_dhcp,
    "winsock_reset": repair_winsock_reset,
}


def run_repair(repair_id: str) -> RepairResult:
    fn = REPAIR_FUNCS.get(repair_id)
    if not fn:
        return RepairResult(repair_id, False, "Reparacion desconocida")
    try:
        return fn()
    except Exception as e:
        return RepairResult(repair_id, False, str(e))
