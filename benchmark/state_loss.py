#!/usr/bin/env python3
"""Stage 4 state-loss preview: temporarily hide local state and restore it.

Prerequisite: deploy the selected tier and tool MANUALLY first; do not run
bench.py, since bench.py destroys deployments before this test can inspect them.
Without --execute this program does not modify files or call AWS.
IMPORTANT: Never apply a plan while state is hidden. This tool restores state
in a finally block but an OS crash can still require recovery from the backup.
"""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIERS = {"simple": "01-simple", "medium": "02-medium", "intensive": "03-intensive"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tier", default="simple", choices=TIERS)
    p.add_argument("--tool", required=True, choices=("cloudformation", "terraform", "opentofu", "pulumi"))
    p.add_argument("--profile")
    p.add_argument("--execute", action="store_true", help="Move existing LOCAL state temporarily")
    args = p.parse_args()
    work = ROOT / "tiers" / TIERS[args.tier] / args.tool
    if args.tool == "cloudformation":
        print("CloudFormation has NO local state to hide. Its state is AWS-managed.")
        print("For an actual AWS-side comparison inspect: aws cloudformation describe-stacks")
        return
    path = work / (".pulumi-state" if args.tool == "pulumi" else "terraform.tfstate")
    backup = ROOT / "results" / "state-backups" / f"{args.tier}-{args.tool}"
    if not path.exists():
        sys.exit(f"No local state found at {path}. Manually deploy this tier first.")
    print(f"State: {path}\nBackup outside tool directory: {backup}")
    if not args.execute:
        print("Dry mode. Use --execute to run the state-loss preview and automatic restore.")
        return
    if backup.exists():
        sys.exit(f"Refusing to overwrite existing backup {backup}; recover/remove it manually.")
    backup.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(AWS_REGION="us-east-1", AWS_DEFAULT_REGION="us-east-1",
               AWS_PAGER="", TF_IN_AUTOMATION="1", PULUMI_CONFIG_PASSPHRASE="",
               PULUMI_BACKEND_URL=(work / ".pulumi-state").as_uri())
    if args.profile:
        env["AWS_PROFILE"] = args.profile
    log = ROOT / "results" / "logs" / f"state-loss-{args.tier}-{args.tool}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(backup))
    print("Temporarily hid state; running PREVIEW ONLY (no apply).")
    try:
        if args.tool in ("terraform", "opentofu"):
            cmd = ["terraform" if args.tool == "terraform" else "tofu", "plan", "-refresh=false",
                   "-input=false", "-no-color", "-detailed-exitcode"]
        else:
            cmd = ["pulumi", "preview", "--non-interactive", "--stack", "dev"]
        with log.open("w") as fh:
            result = subprocess.run(cmd, cwd=work, env=env, stdout=fh, stderr=subprocess.STDOUT)
        print(f"Preview exit code: {result.returncode}. Log: {log}")
        if args.tool in ("terraform", "opentofu"):
            print("Terraform/OpenTofu exit 2 means proposed changes; NO apply was executed.")
        else:
            print("Pulumi may report that the stack no longer exists in the hidden local backend.")
    finally:
        # Pulumi may have recreated an empty backend on preview. Remove ONLY its new
        # directory; do not touch the backup copy.
        if path.exists():
            if args.tool == "pulumi" and path.is_dir():
                shutil.rmtree(path)
            else:
                print(f"WARNING: unexpected state at {path}; backup remains at {backup}")
                sys.exit(2)
        shutil.move(str(backup), str(path))
        print("Original state RESTORED; safe to run a normal preview / destroy.")

if __name__ == "__main__":
    main()
