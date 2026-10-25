"""Collect local verification evidence without creating AWS resources."""
from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def main():
    logs = OUT / "logs"
    logs.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", AWS_PAGER="",
               AWS_EC2_METADATA_DISABLED="true", AWS_MAX_ATTEMPTS="1")
    records = []

    def run(name, args, category, expected_failure=False):
        start = time.perf_counter()
        try:
            result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=120)
            code = result.returncode
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired as exc:
            code = None
            output = "TIMEOUT after 120 seconds\n"
            for part in (exc.stdout, exc.stderr):
                if part:
                    output += part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part
        path = logs / f"{name}.log"
        path.write_text("$ " + subprocess.list2cmdline(args) + "\n\n" + output, encoding="utf-8")
        status = "passed" if code == 0 else "blocked" if expected_failure else "failed"
        if category == "schema" and code in (4, 8, 12):
            status = "warning"
        record = dict(name=name, category=category, status=status, exit_code=code,
                      elapsed_s=round(time.perf_counter() - start, 3),
                      command=args, log=path.relative_to(OUT).as_posix())
        records.append(record)
        print(f"{name}: {status} (exit {code}); {record['log']}", flush=True)

    tools = {name: shutil.which(name) for name in ("aws", "terraform", "tofu", "pulumi", "cfn-lint")}
    run("unit-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], "tests")
    run("preflight", [sys.executable, "benchmark/bench.py", "preflight"], "prerequisites", True)
    for tier in ("simple", "medium", "intensive"):
        run(f"dry-run-{tier}", [sys.executable, "benchmark/bench.py", "run", "--tier", tier,
                               "--runs", "1", "--dry-run"], "simulation")
    for tool in ("cloudformation", "terraform", "opentofu", "pulumi"):
        run(f"failure-dry-run-{tool}", [sys.executable, "benchmark/failure.py", "--tool", tool], "simulation")
        run(f"state-loss-check-{tool}", [sys.executable, "benchmark/state_loss.py", "--tool", tool],
            "prerequisites", tool != "cloudformation")
    if tools["aws"]:
        run("aws-version", [tools["aws"], "--version"], "environment")
    if tools["cfn-lint"]:
        run("cfn-lint-version", [tools["cfn-lint"], "--version"], "environment")
        templates = sorted(ROOT.glob("tiers/*/cloudformation/*.yaml"))
        templates += sorted(ROOT.glob("experiments/*/cloudformation/*.yaml"))
        for template in templates:
            name = "lint-" + "-".join(template.relative_to(ROOT).with_suffix("").parts)
            run(name, [tools["cfn-lint"], "--regions", "us-east-1", "--template", str(template)], "schema")
            if tools["aws"]:
                name = "aws-validate-" + "-".join(template.relative_to(ROOT).with_suffix("").parts)
                run(name, [tools["aws"], "cloudformation", "validate-template", "--region", "us-east-1",
                           "--template-body", "file://" + str(template), "--output", "json",
                           "--cli-connect-timeout", "10", "--cli-read-timeout", "30"], "aws-template-validation")

    spec = importlib.util.spec_from_file_location("bench", ROOT / "benchmark/bench.py")
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    loc_rows = [dict(tier=tier, tool=tool, loc=bench.count_loc(tool, ROOT / "tiers" / folder / tool))
                for tier, folder in bench.TIER_DIRS.items() for tool in bench.TOOLS]
    with (OUT / "source-metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["tier", "tool", "loc"])
        writer.writeheader()
        writer.writerows(loc_rows)
    payload = dict(timestamp=datetime.now(timezone.utc).isoformat(), python=sys.version,
                   tools=tools, aws_resources_created=False, executions=records, source_metrics=loc_rows)
    (OUT / "execution-summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = ["# Resultados locales", "", f"Fecha UTC: {payload['timestamp']}", "",
             "No se crearon recursos AWS. No hay mediciones reales de despliegue, destruccion,",
             "estado, disponibilidad HTTP ni costos. Los dry-run no son benchmarks de rendimiento.", "",
             "## Entorno", "", f"Python: {sys.version.split()[0]}", ""]
    lines += [f"- `{name}`: {'disponible' if path else 'no instalado / no encontrado en PATH'}"
              for name, path in tools.items()]
    lines += ["", "## Ejecuciones", "", "Los tiempos de ejecucion locales estan en execution-summary.json; no son latencias IaC.", "",
              "| Comprobacion | Categoria | Resultado | Exit | Log |", "|---|---|---|---|---|"]
    lines += [f"| {r['name']} | {r['category']} | {r['status']} | {r['exit_code']} | [{r['log']}]({r['log']}) |"
              for r in records]
    lines += ["", "## Lineas de codigo", "", "Calculadas con count_loc del benchmark original; excluye blancos y comentarios.", "",
              "| Nivel | Herramienta | LOC |", "|---|---|---|"]
    lines += [f"| {r['tier']} | {r['tool']} | {r['loc']} |" for r in loc_rows]
    lines += ["", "## Interpretacion", "",
              "- passed indica que el comando termino con codigo 0, no que hubo un despliegue exitoso.",
              "- blocked identifica prerrequisitos ausentes; consultar el log para la causa concreta.",
              "- failed en cfn-lint puede incluir advertencias; consultar diagnosticos y codigo de salida.",
              "- warning en cfn-lint indica advertencias o mensajes informativos sin errores de esquema.",
              "- cfn-lint W3691 advierte que PostgreSQL '16' esta deprecado en medium e intensive; verificar una version menor admitida antes del despliegue.",
              "- AWS validate-template comprueba la plantilla, pero no demuestra que servicios, permisos o versiones de motor permitan desplegarla.",
              "- preflight pudo autenticar la identidad AWS; esta bloqueado por las tres CLI ausentes, no por falta de credenciales.",
              "- CloudFormation no tiene estado local; su comprobacion de state-loss es informativa.",
              "- La prueba de perdida de estado requiere un despliegue manual previo. No se fabrico estado para ejecutarla.",
              "- No se ejecutaron failure --execute, modularidad ni cifrado: requieren AWS o herramientas ausentes.",
              "- No se genero results.csv del benchmark: reservarlo para mediciones reales, no simulaciones.",
              "- No hay base para clasificar herramientas por velocidad ni calcular medianas de despliegue.", "",
              "## Reproduccion", "", "`python results/run_local.py` repite estas comprobaciones y reemplaza sus evidencias locales.", ""]
    (OUT / "local-results.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
