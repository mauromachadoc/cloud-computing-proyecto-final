#!/usr/bin/env python3
"""iacbench - benchmark harness for CloudFormation / Terraform / OpenTofu / Pulumi.

For every (tier, tool) it runs N cycles of:
    preview  -> deploy -> no-op preview -> destroy
and records wall-clock time, lines of code, resource count and state footprint.
Results are appended to results/results.csv and summarised in results/results.md.

Examples
    python benchmark/bench.py preflight
    python benchmark/bench.py run --tier simple --runs 3 --profile account-a
    python benchmark/bench.py run --tier simple --tools terraform,pulumi --runs 1 --dry-run
    python benchmark/bench.py report

WARNING: `run` creates REAL AWS resources (it destroys them at the end of each cycle).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
LOGS_DIR = RESULTS_DIR / "logs"
CSV_PATH = RESULTS_DIR / "results.csv"
MD_PATH = RESULTS_DIR / "results.md"

REGION = "us-east-1"
TIER_DIRS = {"simple": "01-simple", "medium": "02-medium", "intensive": "03-intensive"}
TOOLS = ["cloudformation", "terraform", "opentofu", "pulumi"]

# ROUGH hourly cost estimates (USD) while a tier is deployed. Used only to track your
# credit burn - verify with the AWS Pricing Calculator and edit if needed.
TIER_HOURLY_USD_EST = {"simple": 0.02, "medium": 0.15, "intensive": 0.50}

CSV_FIELDS = [
    "timestamp", "tier", "tool", "run", "aws_account", "ok", "failed_step",
    "init_s", "preview_s", "deploy_s", "noop_preview_s", "destroy_s",
    "loc", "resources", "state_kind", "state_bytes", "est_cost_usd",
]

LOC_GLOBS = {
    "cloudformation": ["*.yaml", "*.yml", "*.json"],
    "terraform": ["*.tf"],
    "opentofu": ["*.tf"],
    "pulumi": ["*.py", "Pulumi.yaml", "requirements.txt"],
}
COMMENT_PREFIX = {"cloudformation": "#", "terraform": "#", "opentofu": "#", "pulumi": "#"}
IGNORED_PARTS = {"venv", ".terraform", "__pycache__", ".pulumi-state"}


# --------------------------------------------------------------------------- helpers
class StepFailed(Exception):
    def __init__(self, step: str, detail: str = ""):
        super().__init__(f"{step}: {detail}")
        self.step = step


class Ctx:
    def __init__(self, tier: str, tool: str, run_no: int, profile: str | None, dry: bool):
        self.tier, self.tool, self.run_no, self.dry = tier, tool, run_no, dry
        self.dir = ROOT / "tiers" / TIER_DIRS[tier] / tool
        self.stack = f"iacbench-{tier}-{tool}"
        self.log = LOGS_DIR / f"{tier}-{tool}-run{run_no}.log"
        self.env = os.environ.copy()
        self.env.update({
            "AWS_REGION": REGION,
            "AWS_DEFAULT_REGION": REGION,
            "AWS_PAGER": "",
            "TF_IN_AUTOMATION": "1",
            "PULUMI_SKIP_UPDATE_CHECK": "true",
            "PULUMI_CONFIG_PASSPHRASE": "",
            "PULUMI_BACKEND_URL": (self.dir / ".pulumi-state").resolve().as_uri(),
        })
        if profile:
            self.env["AWS_PROFILE"] = profile


def sh(ctx: Ctx, cmd: list[str], ok_codes=(0,), cwd: Path | None = None) -> float:
    """Run a command, append its output to the log, return elapsed seconds."""
    printable = " ".join(cmd)
    print(f"      $ {printable}")
    if ctx.dry:
        return 0.0
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    with open(ctx.log, "a") as fh:
        fh.write(f"\n$ {printable}\n")
        fh.flush()
        proc = subprocess.run(cmd, cwd=cwd or ctx.dir, env=ctx.env, stdout=fh,
                              stderr=subprocess.STDOUT, text=True)
    elapsed = time.perf_counter() - start
    if proc.returncode not in ok_codes:
        raise StepFailed(printable, f"exit code {proc.returncode} (see {ctx.log})")
    return elapsed


def capture(ctx: Ctx, cmd: list[str], cwd: Path | None = None) -> str:
    if ctx.dry:
        return ""
    res = subprocess.run(cmd, cwd=cwd or ctx.dir, env=ctx.env, capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


def count_loc(tool: str, tool_dir: Path) -> int:
    """Non-blank, non-comment lines of IaC source (lock files / venvs excluded)."""
    files: set[Path] = set()
    for pattern in LOC_GLOBS[tool]:
        for path in tool_dir.rglob(pattern):
            if not (set(path.relative_to(tool_dir).parts) & IGNORED_PARTS):
                files.add(path)
    prefix = COMMENT_PREFIX[tool]
    total = 0
    for path in files:
        for line in path.read_text(errors="ignore").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(prefix):
                total += 1
    return total


def aws_account(ctx: Ctx) -> str:
    out = capture(ctx, ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"], cwd=ROOT)
    return out.strip() or "dry-run"


def dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.exists() else 0


# --------------------------------------------------------------------------- tool adapters
class CloudFormation:
    name = "cloudformation"

    def __init__(self, ctx: Ctx):
        self.c = ctx
        self.tpl = f"file://{ctx.dir / 'template.yaml'}"
        self.cs = f"{ctx.stack}-cs"

    def setup(self) -> float:
        return sh(self.c, ["aws", "cloudformation", "validate-template", "--template-body", self.tpl])

    def preview(self) -> float:
        t = sh(self.c, ["aws", "cloudformation", "create-change-set", "--stack-name", self.c.stack,
                        "--change-set-name", self.cs, "--change-set-type", "CREATE",
                        "--template-body", self.tpl, "--capabilities", "CAPABILITY_NAMED_IAM"])
        return t + sh(self.c, ["aws", "cloudformation", "wait", "change-set-create-complete",
                               "--stack-name", self.c.stack, "--change-set-name", self.cs])

    def deploy(self) -> float:
        t = sh(self.c, ["aws", "cloudformation", "execute-change-set",
                        "--stack-name", self.c.stack, "--change-set-name", self.cs])
        return t + sh(self.c, ["aws", "cloudformation", "wait", "stack-create-complete",
                               "--stack-name", self.c.stack])

    def noop_preview(self) -> float:
        return sh(self.c, ["aws", "cloudformation", "deploy", "--stack-name", self.c.stack,
                           "--template-file", str(self.c.dir / "template.yaml"),
                           "--capabilities", "CAPABILITY_NAMED_IAM", "--no-execute-changeset",
                           "--no-fail-on-empty-changeset"])

    def destroy(self) -> float:
        t = sh(self.c, ["aws", "cloudformation", "delete-stack", "--stack-name", self.c.stack])
        return t + sh(self.c, ["aws", "cloudformation", "wait", "stack-delete-complete",
                               "--stack-name", self.c.stack])

    def resources(self) -> int:
        out = capture(self.c, ["aws", "cloudformation", "describe-stack-resources", "--stack-name",
                               self.c.stack, "--query", "length(StackResources)", "--output", "text"])
        return int(out.strip() or 0)

    def state(self) -> tuple[str, int]:
        return ("AWS-managed (no local file)", 0)


class Terraform:
    name = "terraform"
    binary = "terraform"

    def __init__(self, ctx: Ctx):
        self.c = ctx
        self.b = self.binary

    def setup(self) -> float:
        return sh(self.c, [self.b, "init", "-input=false", "-no-color"])

    def preview(self) -> float:
        return sh(self.c, [self.b, "plan", "-out=tfplan", "-input=false", "-no-color"])

    def deploy(self) -> float:
        return sh(self.c, [self.b, "apply", "-input=false", "-no-color", "tfplan"])

    def noop_preview(self) -> float:
        return sh(self.c, [self.b, "plan", "-input=false", "-no-color", "-detailed-exitcode"], ok_codes=(0, 2))

    def destroy(self) -> float:
        return sh(self.c, [self.b, "destroy", "-auto-approve", "-input=false", "-no-color"])

    def resources(self) -> int:
        out = capture(self.c, [self.b, "state", "list"])
        return len([ln for ln in out.splitlines() if ln and not ln.startswith("data.")])

    def state(self) -> tuple[str, int]:
        f = self.c.dir / "terraform.tfstate"
        return ("local terraform.tfstate", f.stat().st_size if f.exists() else 0)


class OpenTofu(Terraform):
    name = "opentofu"
    binary = "tofu"


class Pulumi:
    name = "pulumi"

    def __init__(self, ctx: Ctx):
        self.c = ctx

    def setup(self) -> float:
        if not self.c.dry:
            (self.c.dir / ".pulumi-state").mkdir(exist_ok=True)
        t = sh(self.c, ["pulumi", "login", (self.c.dir / ".pulumi-state").resolve().as_uri()])
        t += sh(self.c, ["pulumi", "install"])
        t += sh(self.c, ["pulumi", "stack", "select", "dev", "--create"])
        t += sh(self.c, ["pulumi", "config", "set", "aws:region", REGION, "--stack", "dev"])
        return t

    def preview(self) -> float:
        return sh(self.c, ["pulumi", "preview", "--non-interactive", "--stack", "dev"])

    def deploy(self) -> float:
        return sh(self.c, ["pulumi", "up", "--yes", "--skip-preview", "--non-interactive", "--stack", "dev"])

    def noop_preview(self) -> float:
        return self.preview()

    def destroy(self) -> float:
        return sh(self.c, ["pulumi", "destroy", "--yes", "--skip-preview", "--non-interactive", "--stack", "dev"])

    def resources(self) -> int:
        out = capture(self.c, ["pulumi", "stack", "export", "--stack", "dev"])
        if not out:
            return 0
        res = json.loads(out).get("deployment", {}).get("resources", [])
        return len([r for r in res if not r["type"].startswith(("pulumi:pulumi:Stack", "pulumi:providers:"))])

    def state(self) -> tuple[str, int]:
        return ("local file backend (.pulumi-state/)", dir_size(self.c.dir / ".pulumi-state"))


ADAPTERS = {"cloudformation": CloudFormation, "terraform": Terraform, "opentofu": OpenTofu, "pulumi": Pulumi}


# --------------------------------------------------------------------------- orchestration
def preflight(profile: str | None) -> int:
    ctx = Ctx("simple", "terraform", 0, profile, dry=False)
    ok = True
    needs = {"aws": "AWS CLI v2", "terraform": "Terraform", "tofu": "OpenTofu", "pulumi": "Pulumi CLI"}
    print(f"  [ok] Python {sys.version.split()[0]} ({sys.executable})")
    for exe, label in needs.items():
        path = shutil.which(exe)
        print(f"  [{'ok' if path else 'MISSING'}] {label} ({exe})")
        ok &= bool(path)
    if shutil.which("aws"):
        out = capture(ctx, ["aws", "sts", "get-caller-identity", "--output", "json"], cwd=ROOT)
        if out:
            ident = json.loads(out)
            print(f"  [ok] AWS identity: account {ident['Account']} / {ident['Arn']}  (region forced to {REGION})")
        else:
            print("  [FAIL] Could not call sts:GetCallerIdentity - check credentials / --profile")
            ok = False
    print("\nReminder: set an AWS Budgets alert BEFORE running the benchmarks.")
    return 0 if ok else 1


def verify_http(ctx: Ctx) -> None:
    """Check the application separately from IaC deployment timing."""
    if ctx.dry:
        return
    if ctx.tool == "cloudformation":
        url = capture(ctx, ["aws", "cloudformation", "describe-stacks", "--stack-name", ctx.stack,
                            "--query", "Stacks[0].Outputs[?OutputKey=='SiteUrl'].OutputValue | [0]",
                            "--output", "text"]).strip()
    elif ctx.tool == "pulumi":
        url = capture(ctx, ["pulumi", "stack", "output", "site_url", "--stack", "dev"]).strip()
    else:
        binary = "tofu" if ctx.tool == "opentofu" else "terraform"
        url = capture(ctx, [binary, "output", "-raw", "site_url"]).strip()
    start = time.perf_counter()
    evidence = {"url": url, "ok": False, "error": "No site URL returned"}
    while url.startswith(("http://", "https://")) and time.perf_counter() - start < 300:
        try:
            with urlopen(url, timeout=10) as response:
                body = response.read(1024 * 1024).decode("utf-8", errors="replace")
                if response.status == 200 and "<title>Pong | Single Player | By Bocaletto Luca</title>" in body:
                    evidence.update(ok=True, status=response.status, error="")
                    break
                evidence["error"] = "Response did not contain the Pong page title"
        except (URLError, OSError) as exc:
            evidence["error"] = str(exc)
        time.sleep(5)
    evidence["elapsed_s"] = round(time.perf_counter() - start, 2)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / f"{ctx.tier}-{ctx.tool}-run{ctx.run_no}-http.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"      HTTP verification: {'ok' if evidence['ok'] else 'FAILED'} ({path})")
    if not evidence["ok"]:
        raise StepFailed("http_verification", evidence["error"])


def run_cycle(tier: str, tool: str, run_no: int, profile: str | None, dry: bool, skip_setup: bool,
              check_http: bool = False) -> dict:
    ctx = Ctx(tier, tool, run_no, profile, dry)
    ad = ADAPTERS[tool](ctx)
    row = {k: "" for k in CSV_FIELDS}
    row.update(timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"), tier=tier, tool=tool,
               run=run_no, aws_account=aws_account(ctx), ok=True, loc=count_loc(tool, ctx.dir))
    deployed = False
    preview_started = False
    try:
        if not skip_setup:
            row["init_s"] = round(ad.setup(), 2)
        preview_started = True
        row["preview_s"] = round(ad.preview(), 2)
        deployed = True  # set BEFORE deploy: a half-failed deploy still needs cleanup
        row["deploy_s"] = round(ad.deploy(), 2)
        row["noop_preview_s"] = round(ad.noop_preview(), 2)
        row["resources"] = ad.resources()
        row["state_kind"], row["state_bytes"] = ad.state()
        if check_http:
            verify_http(ctx)
        row["destroy_s"] = round(ad.destroy(), 2)
        deployed = False
    except StepFailed as exc:
        row["ok"], row["failed_step"] = False, exc.step
        print(f"      !! FAILED: {exc}")
    finally:
        # A CloudFormation CREATE change set can leave a REVIEW_IN_PROGRESS
        # stack even when its preview/wait fails. Clean it up in that case.
        should_cleanup = deployed
        if tool == "cloudformation" and preview_started and not deployed and not dry:
            existing = capture(ctx, ["aws", "cloudformation", "describe-stacks",
                                     "--stack-name", ctx.stack, "--query",
                                     "Stacks[0].StackStatus", "--output", "text"])
            should_cleanup = bool(existing.strip())
        if should_cleanup and not dry:
            print("      cleaning up after failure ...")
            try:
                ad.destroy()
            except StepFailed as exc:
                print(f"      !! CLEANUP FAILED - check the AWS console for leftovers: {exc}")
    live_s = sum(float(row[k] or 0) for k in ("deploy_s", "noop_preview_s", "destroy_s"))
    row["est_cost_usd"] = round(TIER_HOURLY_USD_EST[tier] * live_s / 3600, 4)
    return row


def append_csv(rows: list[dict]) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    new = not CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        if new:
            writer.writeheader()
        writer.writerows(rows)


def med(values: list[float]) -> str:
    return f"{statistics.median(values):.1f}" if values else "-"


def report() -> None:
    if not CSV_PATH.exists():
        sys.exit("No results yet: run the benchmark first.")
    with open(CSV_PATH) as fh:
        rows = [r for r in csv.DictReader(fh)]
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["tier"], r["tool"]), []).append(r)
    lines = [
        "# Benchmark results", "",
        f"_Generated {datetime.now().isoformat(timespec='seconds')} - times are medians of successful runs, in seconds._", "",
        "| Tier | Tool | Runs ok/total | LOC | Resources | Preview (s) | Deploy (s) | No-op preview (s) | Destroy (s) | State | Est. cost/run (USD) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for tier in TIER_DIRS:
        for tool in TOOLS:
            g = groups.get((tier, tool))
            if not g:
                continue
            good = [r for r in g if r["ok"] == "True"]

            def col(name: str) -> list[float]:
                return [float(r[name]) for r in good if r[name] not in ("", None)]

            last = good[-1] if good else g[-1]
            cost = sum(float(r["est_cost_usd"] or 0) for r in g) / len(g)
            lines.append(
                f"| {tier} | {tool} | {len(good)}/{len(g)} | {last['loc']} | {last['resources'] or '-'} | "
                f"{med(col('preview_s'))} | {med(col('deploy_s'))} | {med(col('noop_preview_s'))} | "
                f"{med(col('destroy_s'))} | {last['state_kind']} ({last['state_bytes']} B) | {cost:.3f} |"
            )
    historical = RESULTS_DIR / "HISTORICO_SIMPLE_MEDIO.md"
    if historical.exists() and not any(r["tier"] in ("simple", "medium") for r in rows):
        lines += ["", "## Histórico simple/medio", "",
                  "Las ocho corridas de octubre se conservan como informe histórico. Su CSV y logs originales no estaban presentes en este checkout; no se reconstruyeron ni mezclaron con las nuevas mediciones.", "",
                  historical.read_text(encoding="utf-8").replace("# Benchmark results", "### Tabla histórica de octubre de 2026", 1).rstrip()]
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWritten to {MD_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pf = sub.add_parser("preflight", help="check CLIs and AWS credentials")
    pf.add_argument("--profile")
    rn = sub.add_parser("run", help="deploy/measure/destroy (creates REAL AWS resources)")
    rn.add_argument("--tier", required=True, choices=list(TIER_DIRS))
    rn.add_argument("--tools", default=",".join(TOOLS), help="comma-separated subset")
    rn.add_argument("--runs", type=int, default=3)
    rn.add_argument("--start-run", type=int, default=1, help="first run number; use a new number to preserve retry logs")
    rn.add_argument("--profile", help="AWS CLI profile (one per team member account)")
    rn.add_argument("--dry-run", action="store_true", help="print commands only")
    rn.add_argument("--verify-http", action="store_true", help="verify Pong before destroy; timed separately")
    sub.add_parser("report", help="rebuild results/results.md from results.csv")
    args = ap.parse_args()

    if args.cmd == "preflight":
        sys.exit(preflight(args.profile))
    if args.cmd == "report":
        return report()

    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    bad = [t for t in tools if t not in ADAPTERS]
    if bad:
        sys.exit(f"Unknown tools: {bad}. Valid: {TOOLS}")
    est = TIER_HOURLY_USD_EST[args.tier]
    print(f"Tier '{args.tier}' - rough live cost ~${est:.2f}/h while deployed (estimate, verify it).")
    all_rows: list[dict] = []
    for tool in tools:
        for n in range(args.start_run, args.start_run + args.runs):
            print(f"\n=== {args.tier} / {tool} / run {n} ({args.runs} cycles requested) ===")
            # init/setup is timed only on the first run of each tool
            row = run_cycle(args.tier, tool, n, args.profile, args.dry_run, skip_setup=(n > args.start_run),
                            check_http=args.verify_http)
            all_rows.append(row)
            if not args.dry_run:
                append_csv([row])
    if not args.dry_run:
        report()
    else:
        print("\n(dry run: nothing executed, nothing recorded)")


if __name__ == "__main__":
    main()
