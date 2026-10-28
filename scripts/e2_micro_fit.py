"""Ephemeral AMD64 Docker fit experiment; never provisions or uses production secrets."""

import json
import os
import platform
import secrets
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIB = 1024**2
PREFIX = "rmi-e2-fit"
REPORT = {"classification": "NOT VALIDATED", "measurements": {}, "samples": []}
STOP = threading.Event()


def run(*args, timeout=240, check=True):
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=check)


def inspect(name):
    return json.loads(run("docker", "inspect", name).stdout)[0]


def sample():
    while not STOP.is_set():
        for role in ("n8n", "caddy"):
            name = f"{PREFIX}-{role}"
            try:
                info = inspect(name)
                pid = info["State"]["Pid"]
                if not pid:
                    continue
                cg = Path(f"/proc/{pid}/cgroup").read_text().strip().split("::")[-1]
                base = Path("/sys/fs/cgroup") / cg.lstrip("/")
                row = {"role": role, "at": time.time(), "pid": pid}
                for key in ("memory.current", "memory.peak", "memory.swap.current"):
                    row[key] = int((base / key).read_text())
                row["events"] = (base / "memory.events").read_text()
                row["cpu"] = (base / "cpu.stat").read_text()
                row["rss_kib"] = next(
                    int(line.split()[1])
                    for line in Path(f"/proc/{pid}/status").read_text().splitlines()
                    if line.startswith("VmRSS:")
                )
                REPORT["samples"].append(row)
            except (OSError, ValueError, subprocess.SubprocessError, StopIteration):
                pass
        STOP.wait(2)


def timed(label, action):
    started = time.monotonic()
    result = action()
    REPORT["measurements"][label] = round(time.monotonic() - started, 3)
    return result


def ready():
    deadline = time.monotonic() + 360
    while time.monotonic() < deadline:
        if not inspect(f"{PREFIX}-caddy")["State"]["Running"]:
            raise RuntimeError("Caddy exited before readiness; inspect container diagnostic")
        if not inspect(f"{PREFIX}-n8n")["State"]["Running"]:
            raise RuntimeError("n8n exited before readiness; inspect container diagnostic")
        try:
            with urllib.request.urlopen("http://127.0.0.1:18080/healthz/readiness", timeout=5) as r:
                if r.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("n8n readiness deadline exceeded")


def main():
    lock = json.loads((ROOT / "ops/n8n/oci/image-lock.json").read_text())
    images = [
        f"{x['repository']}:{x['version']}@{x['index_digest']}" for x in lock["images"]
    ]
    REPORT.update(architecture=platform.machine(), docker=run("docker", "--version").stdout.strip())
    REPORT["images"] = images
    REPORT["limits"] = {"n8n_mib": 640, "caddy_mib": 64, "cpu_total": .125, "swap": 0}
    REPORT["host_memory"] = "Not representative of a 1 GB VM; not used as fit evidence"
    for image in images:
        timed(f"pull_{images.index(image)}", lambda image=image: run(
            "docker", "pull", "--platform", "linux/amd64", image, timeout=600
        ))
        image_info = json.loads(run("docker", "image", "inspect", image).stdout)[0]
        assert image_info["Architecture"] == "amd64"
    run("docker", "network", "create", "--internal", PREFIX)
    with tempfile.TemporaryDirectory(prefix="rmi-e2-") as folder:
        tmp = Path(folder)
        os.chmod(tmp, 0o755)
        data = tmp / "state"
        data.mkdir(mode=0o700)
        key = tmp / "encryption"
        synthetic_key = secrets.token_hex(32)
        key.write_text(synthetic_key)
        os.chmod(key, 0o400)
        run("sudo", "chown", "1000:1000", str(data), str(key))
        source = ROOT / "ops/n8n/workflows/rome_mobility_orchestration.json"
        original = json.loads(source.read_text())
        assert original["active"] is False
        assert all("credentials" not in n for n in original["nodes"])
        (tmp / "workflow.json").write_text(json.dumps(original))
        synthetic = {
            "id": "e2synthetic001", "name": "CI synthetic HTTP only", "active": False,
            "nodes": [
                {"id": "manual", "name": "Manual", "type": "n8n-nodes-base.manualTrigger",
                 "typeVersion": 1, "position": [0, 0], "parameters": {}},
                {"id": "http", "name": "Mock HTTP", "type": "n8n-nodes-base.httpRequest",
                 "typeVersion": 4.2, "position": [200, 0],
                 "parameters": {"url": f"http://{PREFIX}-caddy:8080/mock", "options": {}}},
            ],
            "connections": {"Manual": {"main": [[
                {"node": "Mock HTTP", "type": "main", "index": 0}
            ]]}},
        }
        (tmp / "synthetic.json").write_text(json.dumps(synthetic))
        (tmp / "Caddyfile").write_text(
            "{\n admin off\n auto_https off\n}\n:8080 {\n"
            ' respond /mock "synthetic-ok" 200\n'
            f" reverse_proxy {PREFIX}-n8n:5678\n}}\n"
        )
        common = [
            "docker", "run", "--name", f"{PREFIX}-n8n", "--platform", "linux/amd64",
            "--network", PREFIX, "--memory", "640m", "--memory-swap", "640m",
            "--cpus", "0.1", "--pids-limit", "256", "--user", "1000:1000",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs", "/home/node/.cache:rw,nosuid,size=32m,uid=1000,gid=1000",
            "-v", f"{data}:/home/node/.n8n", "-v", f"{key}:/run/secrets/key:ro",
            "-v", f"{tmp / 'workflow.json'}:/workflow.json:ro",
            "-v", f"{tmp / 'synthetic.json'}:/synthetic.json:ro",
        ]
        env = {
            "N8N_ENCRYPTION_KEY_FILE": "/run/secrets/key",
            "N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS": "true", "N8N_DIAGNOSTICS_ENABLED": "false",
            "N8N_VERSION_NOTIFICATIONS_ENABLED": "false", "N8N_PERSONALIZATION_ENABLED": "false",
            "N8N_COMMUNITY_PACKAGES_ENABLED": "false", "N8N_LOG_LEVEL": "error",
            "N8N_PROTOCOL": "https", "N8N_SECURE_COOKIE": "true",
            "EXECUTIONS_DATA_SAVE_ON_SUCCESS": "none", "EXECUTIONS_DATA_SAVE_ON_ERROR": "none",
        }
        for k, v in env.items():
            common += ["-e", f"{k}={v}"]
        monitor = threading.Thread(target=sample, daemon=True)
        monitor.start()
        try:
            run("docker", "run", "-d", "--name", f"{PREFIX}-caddy",
                "--platform", "linux/amd64", "--network", PREFIX,
                "--memory", "64m", "--memory-swap", "64m", "--cpus", "0.025",
                "--read-only", "--cap-drop", "ALL", "--cap-add", "NET_BIND_SERVICE",
                "--security-opt", "no-new-privileges",
                "--tmpfs", "/data:size=8m", "--tmpfs", "/config:size=8m",
                "-p", "127.0.0.1:18080:8080",
                "-v", f"{tmp / 'Caddyfile'}:/etc/caddy/Caddyfile:ro", images[1])

            def start():
                run(*common, "-d", images[0])
                ready()

            timed("cold_start", start)
            timed("idle_observation", lambda: time.sleep(300))
            REPORT["idle_stats"] = run("docker", "stats", "--no-stream", "--format", "{{json .}}",
                                       f"{PREFIX}-n8n", f"{PREFIX}-caddy").stdout

            def remove():
                name = f"{PREFIX}-n8n"
                run("docker", "stop", "--time", "30", name)
                state = inspect(name)
                REPORT.setdefault("states", []).append({
                    "state": state["State"], "restarts": state["RestartCount"],
                    "limits": {k: state["HostConfig"][k] for k in
                               ("Memory", "MemorySwap", "NanoCpus")},
                })
                run("docker", "rm", name)

            def cli(label, *args):
                # Stop server first: CLI shares SQLite and the same 640 MiB ceiling.
                started = time.monotonic()
                run(*common, "-d", images[0], *args)
                code = run("docker", "wait", f"{PREFIX}-n8n", timeout=360).stdout.strip()
                REPORT["measurements"][label] = round(time.monotonic() - started, 3)
                remove()
                assert code == "0", f"{label} exited {code}"

            remove()
            cli("import", "import:workflow", "--input=/workflow.json")
            cli("export", "export:workflow", "--all", "--output=/home/node/.n8n/export.json")
            verification = (
                "const fs=require('fs'),a=require('assert');"
                "const w=JSON.parse(fs.readFileSync('/home/node/.n8n/export.json'));"
                "a(w.length>0&&w.every(x=>x.active===false));"
                "a(w.every(x=>x.nodes.every(n=>!('credentials' in n))));"
                "const c=JSON.parse(fs.readFileSync('/home/node/.n8n/config'));"
                "a.strictEqual(c.encryptionKey,fs.readFileSync('/run/secrets/key','utf8'));"
            )
            run(*common, "--rm", "--entrypoint", "node", images[0], "-e", verification)
            REPORT["workflow"] = "Import/export inactive, credential-free and external key PASS"
            timed("restart_readiness", start)
            remove()
            cli("export_after_restart", "export:workflow", "--all",
                "--output=/home/node/.n8n/export.json")
            run(*common, "--rm", "--entrypoint", "node", images[0], "-e", verification)
            REPORT["persistence"] = "PASS (runtime UID 1000, no permission relaxation)"
            cli("synthetic_import", "import:workflow", "--input=/synthetic.json")
            cli("synthetic_execute", "execute", "--id=e2synthetic001")
            REPORT["synthetic_execution"] = "PASS; internal Caddy mock only"
            rows = REPORT["samples"]
            assert rows, "No cgroup evidence collected"
            assert all(r["memory.swap.current"] == 0 for r in rows)
            assert all("oom_kill 0" in r["events"] for r in rows)
            assert all(not s["state"]["OOMKilled"] and s["restarts"] == 0 for s in REPORT["states"])
            peaks = {role: max(r["memory.peak"] for r in rows if r["role"] == role)
                     for role in ("n8n", "caddy")}
            REPORT["peak_bytes"] = peaks
            REPORT["combined_peak_upper_bound"] = sum(peaks.values())
            REPORT["classification"] = (
                "E2 MICRO MARGINAL" if peaks["n8n"] > 544 * MIB
                or REPORT["measurements"]["cold_start"] > 120
                or any(REPORT["measurements"][k] > 120 for k in
                       ("import", "export", "synthetic_execute")) else "E2 MICRO FIT"
            )
        finally:
            STOP.set()
            monitor.join(timeout=15)
            REPORT["final_containers"] = {}
            for role in ("n8n", "caddy"):
                name = f"{PREFIX}-{role}"
                info = run("docker", "inspect", name, check=False)
                if info.returncode == 0:
                    item = json.loads(info.stdout)[0]
                    logs = run("docker", "logs", "--tail", "40", name, check=False)
                    REPORT["final_containers"][role] = {
                        "state": item["State"], "restarts": item["RestartCount"],
                        "diagnostic": (logs.stdout + logs.stderr)[-5000:].replace(
                            synthetic_key, "[synthetic-key-redacted]"
                        ),
                    }
                run("docker", "rm", "-f", f"{PREFIX}-{role}", check=False)
            run("sudo", "rm", "-rf", str(data))  # Only isolated TemporaryDirectory state.
            run("sudo", "chown", str(os.getuid()), str(key))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        REPORT["blocker"] = type(exc).__name__ + ": " + str(exc)[:300]
        REPORT["classification"] = "NOT VALIDATED — inspect failure evidence"
        raise
    finally:
        run("docker", "network", "rm", PREFIX, check=False)
        output = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "e2-fit-report.json"
        output.write_text(json.dumps(REPORT, indent=2))
