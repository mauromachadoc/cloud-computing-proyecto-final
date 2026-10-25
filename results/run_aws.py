"""Run authorized simple/medium benchmarks with persistent execution logs."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import winreg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
LOGS = OUT / "logs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "simple", "medium", "audit"))
    parser.add_argument("--tool", choices=("cloudformation", "terraform", "opentofu", "pulumi"))
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    LOGS.mkdir(exist_ok=True)
    name = args.phase + ("-" + args.tool if args.tool else "")
    if args.background:
        cmd = [sys.executable, "-u", str(Path(__file__).resolve()), args.phase]
        if args.tool:
            cmd += ["--tool", args.tool]
        with (LOGS / f"session-{name}.log").open("a", encoding="utf-8") as stream:
            process = subprocess.Popen(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        print(f"Started {name}: PID {process.pid}; results/logs/session-{name}.log")
        return

    paths = [os.environ.get("PATH", "")]
    for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, r"Environment")):
        with winreg.OpenKey(hive, key) as handle:
            paths.append(os.path.expandvars(winreg.QueryValueEx(handle, "Path")[0]))
    os.environ.update(PATH=";".join(paths), PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                      AWS_REGION="us-east-1", AWS_DEFAULT_REGION="us-east-1", AWS_PAGER="",
                      AWS_EC2_METADATA_DISABLED="true", TF_IN_AUTOMATION="1",
                      PULUMI_SKIP_UPDATE_CHECK="true", PULUMI_CONFIG_PASSPHRASE="")
    records = []
    status_path = OUT / f"session-{name}.json"
    payload = dict(started=datetime.now(timezone.utc).isoformat(), phase=args.phase,
                   tool=args.tool, status="running", commands=records)

    def save():
        status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def run(label, cmd, cwd=ROOT, required=True):
        exe = shutil.which(cmd[0])
        if not exe:
            raise RuntimeError(f"Missing executable: {cmd[0]}")
        command = [exe, *cmd[1:]]
        print(f"\n$ {subprocess.list2cmdline(command)}", flush=True)
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        text = result.stdout + result.stderr
        print(text, flush=True)
        path = LOGS / f"{name}-{label}.log"
        path.write_text("$ " + subprocess.list2cmdline(command) + "\n\n" + text, encoding="utf-8")
        records.append(dict(label=label, command=command, cwd=str(cwd), exit_code=result.returncode,
                            log=path.relative_to(OUT).as_posix()))
        save()
        if result.returncode and required:
            raise RuntimeError(f"{label} failed: exit {result.returncode}")
        return result

    def aws(label, *cmd, required=True):
        return run(label, ["aws", *cmd, "--region", "us-east-1", "--output", "json", "--no-cli-pager"], required=required)

    save()
    benchmark_failed = False
    try:
        identity = json.loads(aws("identity", "sts", "get-caller-identity").stdout)
        if identity["Account"] != "682036276612":
            raise RuntimeError("AWS account differs from the authorized account")
        aws("credits", "freetier", "get-account-plan-state", required=False)
        if args.phase == "audit":
            aws("credit-activities", "freetier", "list-account-activities", required=False)
        if args.phase == "prepare":
            for exe, version in (("terraform", "version"), ("tofu", "version"), ("pulumi", "version"), ("aws", "--version")):
                run(f"version-{exe}", [exe, version])
            run("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
            for tier in ("01-simple", "02-medium"):
                for tool, binary in (("terraform", "terraform"), ("opentofu", "tofu")):
                    folder = ROOT / "tiers" / tier / tool
                    run(f"init-{tier}-{tool}", [binary, "init", "-input=false", "-no-color"], folder)
                    run(f"validate-{tier}-{tool}", [binary, "validate", "-no-color"], folder)
                template = ROOT / "tiers" / tier / "cloudformation" / "template.yaml"
                run(f"lint-{tier}", ["cfn-lint", "--regions", "us-east-1", "--template", str(template)])
        elif args.phase in ("simple", "medium"):
            if not args.tool:
                raise RuntimeError("A single --tool is required to check cleanup between deployments")
            tier = "01-simple" if args.phase == "simple" else "02-medium"
            folder = ROOT / "tiers" / tier / args.tool
            if args.tool in ("terraform", "opentofu"):
                state = folder / "terraform.tfstate"
                if state.exists() and json.loads(state.read_text(encoding="utf-8")).get("resources"):
                    raise RuntimeError("Refusing deployment: pre-existing state requires inspection")
            if args.tool == "cloudformation":
                stacks = json.loads(aws("existing-stacks", "cloudformation", "list-stacks").stdout)
                stack_name = f"iacbench-{args.phase}-cloudformation"
                if any(s["StackName"] == stack_name and s["StackStatus"] != "DELETE_COMPLETE"
                       for s in stacks["StackSummaries"]):
                    raise RuntimeError("Refusing deployment: stack already exists")
            result = run("benchmark", [sys.executable, "benchmark/bench.py", "run", "--tier", args.phase,
                                       "--tools", args.tool, "--runs", "1", "--verify-http"], required=False)
            csv_path = OUT / "results.csv"
            if csv_path.exists():
                with csv_path.open(newline="", encoding="utf-8") as stream:
                    rows = list(csv.DictReader(stream))
                matches = [r for r in rows if r["tier"] == args.phase and r["tool"] == args.tool]
                payload["benchmark_row"] = matches[-1] if matches else None
            if result.returncode or not payload.get("benchmark_row") or payload["benchmark_row"]["ok"] != "True":
                benchmark_failed = True
        if args.phase != "prepare":
            if args.phase == "audit":
                run("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
            checks = [
                ("remaining-vpcs", ("ec2", "describe-vpcs", "--filters", "Name=tag:Name,Values=iacbench-*", "--query", "Vpcs")),
                ("remaining-instances", ("ec2", "describe-instances", "--filters", "Name=tag:Name,Values=iacbench-*",
                                         "Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down", "--query", "Reservations")),
                ("remaining-databases", ("rds", "describe-db-instances", "--query", "DBInstances[?starts_with(DBInstanceIdentifier, 'iacbench-')]")),
                ("remaining-stacks", ("cloudformation", "list-stacks", "--query", "StackSummaries[?starts_with(StackName, 'iacbench-') && StackStatus!='DELETE_COMPLETE']")),
                ("remaining-buckets", ("s3api", "list-buckets", "--query", "Buckets[?starts_with(Name, 'iacbench-')]")),
                ("load-balancers", ("elbv2", "describe-load-balancers", "--query", "LoadBalancers[].{Name:LoadBalancerName,Vpc:VpcId,Arn:LoadBalancerArn}")),
            ]
            if args.phase == "audit":
                checks += [
                    ("remaining-ecs-clusters", ("ecs", "list-clusters", "--query", "clusterArns[?contains(@, ':cluster/iacbench-')]")),
                    ("remaining-task-definitions", ("ecs", "list-task-definitions", "--family-prefix", "iacbench-medium", "--status", "ACTIVE", "--query", "taskDefinitionArns")),
                    ("remaining-iam-roles", ("iam", "list-roles", "--query", "Roles[?starts_with(RoleName, 'iacbench-')].RoleName")),
                    ("remaining-db-snapshots", ("rds", "describe-db-snapshots", "--query", "DBSnapshots[?starts_with(DBInstanceIdentifier, 'iacbench-')].DBSnapshotIdentifier")),
                    ("account-volumes", ("ec2", "describe-volumes", "--query", "Volumes[].{Id:VolumeId,State:State,Size:Size,Attachments:Attachments[].InstanceId}")),
                    ("account-addresses", ("ec2", "describe-addresses", "--query", "Addresses[].{Id:AllocationId,PublicIp:PublicIp}")),
                    ("account-target-groups", ("elbv2", "describe-target-groups", "--query", "TargetGroups[].{Name:TargetGroupName,Vpc:VpcId}")),
                    ("account-rds-secrets", ("secretsmanager", "list-secrets", "--filters", "Key=owning-service,Values=rds", "--query", "SecretList[].{Name:Name,DeletedDate:DeletedDate}")),
                ]
            remaining = []
            for label, command in checks:
                value = json.loads(aws(label, *command).stdout)
                if value and label != "load-balancers" and not label.startswith("account-"):
                    remaining.append(label)
            payload["cleanup_verified"] = not remaining
            if remaining:
                raise RuntimeError(f"Remaining benchmark resources detected: {remaining}; stop before another deployment")
        if benchmark_failed:
            raise RuntimeError("Benchmark did not complete successfully; cleanup checked, inspect logs before retrying")
        payload["status"] = "completed"
    except Exception as exc:
        payload["status"] = "failed"
        payload["error"] = str(exc)
        print(f"ERROR: {exc}", flush=True)
    finally:
        payload["finished"] = datetime.now(timezone.utc).isoformat()
        save()
    if payload["status"] == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
