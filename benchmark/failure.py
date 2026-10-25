#!/usr/bin/env python3
"""Stage 4: intentionally fail a bucket-policy deployment; always try cleanup.

Does not run AWS operations without --execute. Records the expected failure and
cleanup outcome separately, since a failed apply is the point of this test.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ("cloudformation", "terraform", "opentofu", "pulumi")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", required=True, choices=TOOLS)
    parser.add_argument("--profile")
    parser.add_argument("--execute", action="store_true", help="Actually create AWS resources")
    args = parser.parse_args()
    directory = ROOT / "experiments" / "failure" / args.tool
    logs = ROOT / "results" / "logs"
    log = logs / f"failure-{args.tool}.log"
    env = os.environ.copy()
    env.update(AWS_REGION="us-east-1", AWS_DEFAULT_REGION="us-east-1",
               AWS_PAGER="", TF_IN_AUTOMATION="1", PULUMI_CONFIG_PASSPHRASE="",
               PULUMI_BACKEND_URL=(directory / ".pulumi-state").as_uri())
    if args.profile:
        env["AWS_PROFILE"] = args.profile
    stack = f"iacbench-failure-{args.tool}"
    records = []

    def run(label, command, allow_fail=False):
        print(" ", label, ":", " ".join(command))
        if not args.execute:
            return True
        logs.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        with log.open("a", encoding="utf-8") as handle:
            handle.write(f"\n$ {' '.join(command)}\n")
            process = subprocess.run(command, cwd=directory, env=env, stdout=handle,
                                     stderr=subprocess.STDOUT, text=True)
        success = process.returncode == 0
        records.append(dict(step=label, exit_code=process.returncode,
                            elapsed_s=round(time.perf_counter()-start, 2)))
        if not success and not allow_fail:
            print(f"  ERROR at {label}; see {log}")
            raise RuntimeError(label)
        return success

    if not args.execute:
        print("DRY MODE: no AWS calls. Add --execute to run the experiment.")
    failed_as_expected = False
    cleanup_ok = False
    initialized = False
    try:
        if args.tool == "cloudformation":
            # CloudFormation creates the first bucket and then rolls back after
            # S3 rejects the deliberately invalid resource in the policy.
            run("create", ["aws", "cloudformation", "create-stack", "--stack-name", stack,
                "--template-body", f"file://{directory / 'template.yaml'}", "--on-failure", "ROLLBACK"])
            initialized = True
            if args.execute:
                limit = time.monotonic() + 1200
                status = "UNKNOWN"
                while time.monotonic() < limit:
                    p = subprocess.run(["aws", "cloudformation", "describe-stacks", "--stack-name", stack,
                        "--query", "Stacks[0].StackStatus", "--output", "text"],
                        env=env, cwd=directory, capture_output=True, text=True)
                    status = p.stdout.strip() if p.returncode == 0 else "NOT_FOUND"
                    print("  stack:", status)
                    if status in ("ROLLBACK_COMPLETE", "ROLLBACK_FAILED", "CREATE_COMPLETE", "NOT_FOUND"):
                        break
                    time.sleep(15)
                failed_as_expected = status in ("ROLLBACK_COMPLETE", "ROLLBACK_FAILED")
                records.append(dict(step="observe_rollback", status=status))
        elif args.tool in ("terraform", "opentofu"):
            binary = "terraform" if args.tool == "terraform" else "tofu"
            run("init", [binary, "init", "-input=false", "-no-color"])
            initialized = True
            run("preview", [binary, "plan", "-input=false", "-no-color"])
            failed_as_expected = not run("intentional_apply", [binary, "apply", "-auto-approve",
                "-input=false", "-no-color"], allow_fail=True)
        else:
            if args.execute:
                (directory / ".pulumi-state").mkdir(exist_ok=True)
            run("login", ["pulumi", "login", (directory / ".pulumi-state").as_uri()])
            run("install", ["pulumi", "install"])
            run("select", ["pulumi", "stack", "select", "dev", "--create"])
            initialized = True
            run("preview", ["pulumi", "preview", "--stack", "dev", "--non-interactive"])
            failed_as_expected = not run("intentional_up", ["pulumi", "up", "--yes", "--skip-preview",
                "--non-interactive", "--stack", "dev"], allow_fail=True)
    except RuntimeError:
        pass
    finally:
        if initialized or args.execute:
            try:
                if args.tool == "cloudformation":
                    run("delete", ["aws", "cloudformation", "delete-stack", "--stack-name", stack])
                    run("wait_deleted", ["aws", "cloudformation", "wait", "stack-delete-complete",
                        "--stack-name", stack])
                elif args.tool in ("terraform", "opentofu"):
                    binary = "terraform" if args.tool == "terraform" else "tofu"
                    run("destroy", [binary, "destroy", "-auto-approve", "-input=false", "-no-color"])
                else:
                    run("destroy", ["pulumi", "destroy", "--yes", "--skip-preview",
                        "--non-interactive", "--stack", "dev"])
                cleanup_ok = True
            except RuntimeError:
                print("  CLEANUP FAILED: inspect AWS resources and the log immediately.")
    if args.execute:
        output = ROOT / "results" / f"failure-{args.tool}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"tool": args.tool, "timestamp": datetime.now(timezone.utc).isoformat(),
            "failed_as_expected": failed_as_expected, "cleanup_ok": cleanup_ok,
            "steps": records}, indent=2) + "\n")
        print(f"Expected failure: {failed_as_expected}; cleanup succeeded: {cleanup_ok}")
        print(f"Report: {output} | log: {log}")
        if not cleanup_ok or not failed_as_expected:
            sys.exit(1)

if __name__ == "__main__":
    main()
