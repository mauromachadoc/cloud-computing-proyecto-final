"""Prepare only the authorized Pulumi tiers; never deploy or read state."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parent.parent
CLI = Path(r"C:\Program Files (x86)\Pulumi\pulumi.exe")
PYTHON = Path(r"C:\Users\Macha\AppData\Local\Programs\Python\Python312\python.exe")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tier", choices=["simple", "medium"])
    args = parser.parse_args()
    tier_dir = {"simple": "01-simple", "medium": "02-medium"}[args.tier]
    project = ROOT / "tiers" / tier_dir / "pulumi"
    results = ROOT / "results"
    assert project.is_dir() and results.is_dir()
    assert CLI.is_file() and PYTHON.is_file()
    backend = project / ".pulumi-state"
    backend.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update({
        "PULUMI_CONFIG_PASSPHRASE": "",
        "AWS_REGION": "us-east-1",
        "AWS_DEFAULT_REGION": "us-east-1",
        "PULUMI_SKIP_UPDATE_CHECK": "true",
        "AWS_PAGER": "",
        "PULUMI_BACKEND_URL": backend.as_uri(),
        "PULUMI_PYTHON_CMD": str(PYTHON),
        "PATH": str(PYTHON.parent) + os.pathsep + env.get("PATH", ""),
        "NO_COLOR": "1",
    })
    sources = [project / name for name in ("Pulumi.yaml", "requirements.txt", "__main__.py")]
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    summary = {
        "tier": args.tier, "project": str(project), "backend": backend.as_uri(),
        "stack": "dev", "region": "us-east-1", "commands": [],
        "aws_mutations_requested": False,
    }
    summary_path = results / f"pulumi-{args.tier}-summary.json"

    def run(label, command, timeout=300):
        log = results / f"pulumi-{args.tier}-{label}.log"
        record = {"step": label, "command": [str(x) for x in command],
                  "cwd": str(project), "log": str(log), "timeout_seconds": timeout}
        started = time.monotonic()
        with log.open("w", encoding="utf-8") as output:
            output.write("Command: " + subprocess.list2cmdline(record["command"]) + "\n")
            output.flush()
            process = subprocess.Popen(record["command"], cwd=project, env=env,
                                       stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=subprocess.STDOUT)
            try:
                record["exit_code"] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=output, stderr=subprocess.STDOUT, check=False)
                process.wait()
                record.update(exit_code=124, timed_out=True)
        record["duration_seconds"] = round(time.monotonic() - started, 3)
        summary["commands"].append(record)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"{args.tier}: {label}: exit {record['exit_code']} ({record['duration_seconds']}s)", flush=True)
        return record["exit_code"] == 0

    try:
        run("cli-version", [CLI, "version"])
        run("python-version", [PYTHON, "--version"])
        installed = run("install", [CLI, "install", "--non-interactive"], timeout=900)
        venv_python = project / "venv" / "Scripts" / "python.exe"
        if venv_python.is_file():
            run("dependencies", [venv_python, "-m", "pip", "freeze", "--all"])
            run("pip-check", [venv_python, "-m", "pip", "check"])
            run("venv-python-version", [venv_python, "--version"])
        if not installed:
            summary["result"] = "install_failed; preview_not_run"
            return
        for label, command in [
            ("login", [CLI, "login", backend.as_uri(), "--non-interactive"]),
            ("stack-select", [CLI, "stack", "select", "dev", "--create", "--non-interactive"]),
            ("config-region", [CLI, "config", "set", "aws:region", "us-east-1", "--stack", "dev", "--non-interactive"]),
        ]:
            if not run(label, command):
                summary["result"] = f"{label}_failed; preview_not_run"
                return
        success = run("preview", [CLI, "preview", "--non-interactive", "--stack", "dev"], timeout=900)
        summary["result"] = "preview_succeeded" if success else "preview_failed"
        run("plugins", [CLI, "plugin", "ls", "--json"])
    except Exception as exc:
        summary["result"] = "helper_failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        summary["iac_sources_unchanged"] = all(
            hashlib.sha256(p.read_bytes()).hexdigest() == before[p.name] for p in sources
        )
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
