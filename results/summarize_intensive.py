"""Build the intensive report from recorded cycles and a separate cleanup audit."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics

OUT = Path(__file__).resolve().parent
TOOLS = ("cloudformation", "terraform", "opentofu", "pulumi")


def main():
    with (OUT / "results.csv").open(encoding="utf-8", newline="") as stream:
        all_rows = list(csv.DictReader(stream))
    rows = [r for r in all_rows if r["tier"] == "intensive"]
    if {r["tool"] for r in rows} != set(TOOLS):
        raise RuntimeError("Missing intensive tool results")
    audit = json.loads((OUT / "session-audit-intensive.json").read_text(encoding="utf-8"))
    if audit["status"] != "completed" or not audit.get("cleanup_verified"):
        raise RuntimeError("Intensive cleanup audit must pass first")
    audit_lines = ["# Auditoría final del intensivo", "",
                   f"Inicio UTC: {audit['started']}. Fin UTC: {audit['finished']}.", "",
                   "Estado: `completed`; `cleanup_verified=true`. Resumen sin identificadores de cuenta ni recursos. "
                   "Las consultas se realizaron en us-east-1 (CloudFront e IAM tienen alcance global). "
                   "Las colecciones vacías acreditan únicamente los inventarios consultados en ese momento.", "",
                   "| Consulta | Exit | Elementos devueltos |", "|---|---:|---:|"]
    for record in audit["commands"]:
        label = record["label"]
        if label in ("identity", "credits", "credit-activities", "tests"):
            continue
        log = (OUT / record["log"]).read_text(encoding="utf-8")
        value = json.loads(log.split("\n\n", 1)[1])
        count = 0 if value is None else len(value)
        audit_lines.append(f"| {label} | {record['exit_code']} | {count} |")
    audit_lines += ["", "Fuentes locales: `session-audit-intensive.json` y `logs/audit-intensive-*.log`. "
                    "No se eliminaron recursos ajenos al benchmark. El saldo de créditos y las recompensas no se usan para inferir la factura.", ""]
    (OUT / "AUDITORIA_INTENSIVO.md").write_text("\n".join(audit_lines), encoding="utf-8")
    # Keep reviewable measurements in Git without the AWS account identifier.
    fields = [field for field in rows[0] if field != "aws_account"]
    with (OUT / "intensive-results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    good = [r for r in rows if r["ok"] == "True"]
    historical_medium = {}
    for line in (OUT / "RESULTADOS_REALES.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("| medium |"):
            cells = [value.strip() for value in line.strip("|").split("|")]
            historical_medium[cells[1]] = dict(deploy_s=cells[4], destroy_s=cells[6])
    http = {}
    for r in good:
        key = f"intensive-{r['tool']}-run{r['run']}"
        evidence = json.loads((OUT / "logs" / f"{key}-http.json").read_text(encoding="utf-8"))
        if not evidence["ok"] or evidence.get("status") != 200:
            raise RuntimeError(f"Missing successful application verification: {key}")
        http[key] = evidence
    lines = ["## Intensivo: ejecución real", "",
             f"Actualizado UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.", "",
             f"Se registraron {len(rows)} intentos intensivos secuenciales en AWS us-east-1, de los cuales {len(good)} completaron el ciclo con verificación de Pong y destrucción. "
             "Los informes de las ocho corridas simple/medio del 25/10/2026 se conservan como evidencia histórica; su CSV y logs originales no estaban en este checkout y no se reconstruyeron. "
             "La exclusión histórica del intensivo fue reemplazada por la solicitud de ejecutarlo. No se ejecutó la etapa 4.", "",
             "### Mediciones intensivas", "",
             "Segundos de pared del orquestador; HTTP/HTTPS se mide por separado. «—» indica una etapa sin medición registrada, no cero segundos. "
             "Los intentos fallidos quedan fuera de las medianas de éxito.", "",
             "| Herramienta | Corrida | OK | Init | Preview | Deploy | No-op | Destroy | LOC | Recursos | Estado (B) |",
             "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        cells = [r[k] or "—" for k in ("tool", "run", "ok", "init_s", "preview_s", "deploy_s", "noop_preview_s", "destroy_s", "loc", "resources", "state_bytes")]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "LOC depende del formato y no mide legibilidad ni modularidad. Los recursos son unidades lógicas de cada proveedor, no un conteo homogéneo de servicios AWS. "
              "Los 0 B de CloudFormation significan estado administrado por AWS; HCL mide un archivo y Pulumi el directorio completo de su backend. Sus bytes no prueban eficiencia relativa.", "",
              "### Verificación y fallos", ""]
    for r in rows:
        key = f"intensive-{r['tool']}-run{r['run']}"
        if r["ok"] == "True":
            evidence = http[key]
            lines.append(f"- {r['tool']}, corrida {r['run']}: HTTPS 200 y título de Pong; comprobación en {evidence['elapsed_s']} s, fuera de deploy.")
        else:
            lines.append(f"- {r['tool']}, corrida {r['run']}: falló `{r['failed_step']}`. Ver `logs/{key}.log`; no se interpreta como ciclo exitoso.")
            if r["tool"] == "cloudformation" and r["run"] == "1" and r["failed_step"] == "http_verification":
                lines.append("  El proceso inicial había cargado el verificador que solo admitía HTTP antes de aplicar la corrección HTTPS. El rechazo no prueba indisponibilidad del sitio. La corrida se conserva como fallida; el reintento usa código corregido y otro número de log. La limpieza del intento inicial no tenía cronómetro registrado en el CSV.")
    lines += ["", "### Comparación descriptiva", ""]
    for tool in TOOLS:
        samples = [r for r in good if r["tool"] == tool]
        medium = [r for r in all_rows if r["tier"] == "medium" and r["tool"] == tool and r["ok"] == "True"]
        if not medium and tool in historical_medium:
            medium = [historical_medium[tool]]
        if samples and medium:
            deploy = statistics.median(float(r["deploy_s"]) for r in samples)
            destroy = statistics.median(float(r["destroy_s"]) for r in samples)
            lines.append(f"- {tool}: deploy intensivo {deploy:.2f} s ({deploy / float(medium[-1]['deploy_s']):.2f} veces el medio); destroy {destroy:.2f} s ({destroy / float(medium[-1]['destroy_s']):.2f} veces el medio).")
    events_path = OUT / "logs" / "intensive-cloudformation-run2-events.json"
    if events_path.exists():
        events = json.loads(events_path.read_text(encoding="utf-8-sig"))["StackEvents"]
        lines += ["", "Duración de creación por eventos CloudFormation, segundo intento (primer CREATE_IN_PROGRESS a CREATE_COMPLETE):", "",
                  "| Recurso lógico | Segundos |", "|---|---:|"]
        for name in ("Database", "Redis", "Alb", "CloudFrontDistribution", "AutoScalingGroup"):
            starts = [datetime.fromisoformat(e["Timestamp"]) for e in events if e["LogicalResourceId"] == name and e["ResourceStatus"] == "CREATE_IN_PROGRESS"]
            ends = [datetime.fromisoformat(e["Timestamp"]) for e in events if e["LogicalResourceId"] == name and e["ResourceStatus"] == "CREATE_COMPLETE"]
            if starts and ends:
                lines.append(f"| {name} | {(max(ends) - min(starts)).total_seconds():.2f} |")
        lines += ["", "RDS fue la última dependencia en completar su creación en este intento. "
                  "Las operaciones se solapan y no deben sumarse; estos eventos no aíslan el overhead del motor. "
                  "La creación del ASG no equivale a readiness HTTP de sus instancias. Fuente: `logs/intensive-cloudformation-run2-events.json`."]
    lines += ["", "La referencia medio proviene de la tabla histórica de `RESULTADOS_REALES.md`; el intensivo proviene del CSV nuevo. "
              "Son observaciones de ejecuciones individuales, en fechas distintas y con servicios diferentes: no estiman dispersión ni permiten generalizar un ranking. "
              "El intensivo agrega NAT, EC2/ASG, RDS Multi-AZ, Redis con réplica, CloudFront y alarmas. "
              "No se midió carga intensiva de usuarios: «intensivo» designa la complejidad de infraestructura. "
              "Pong no consume RDS ni Redis; HTTPS no prueba failover, autoescalado, caché ni disponibilidad sostenida.", "",
              "### Preparación y trazabilidad", "",
              "- Se corrigió el bloque HCL anidado `restrictions/geo_restriction` en Terraform y OpenTofu; ambos pasaron init/validate.",
              "- CLI: Terraform 1.16.6, OpenTofu 1.13.1, Pulumi 3.272.0; orquestador Python 3.12.10. Proveedor AWS HCL 5.100.0 y Pulumi AWS 6.83.4. Ver `logs/intensive-version-*.log` y los logs de init/install.",
              "- El verificador ahora acepta HTTPS para CloudFront. Se agregó una prueba de regresión y `--start-run` para conservar logs de reintentos.",
              "- `intensive-results.csv` conserva las mediciones versionables del CSV original, omitiendo solo el identificador de cuenta. Los logs y auditorías JSON quedan locales según `.gitignore`.",
              "- Ver `pulumi-intensive-summary.json` y `pulumi-intensive-dependencies.log` para preparación y versiones de Pulumi.",
              "- Init intensivo HCL/Pulumi reutiliza la preparación previa; no mide instalación desde cero.", "",
              "En el segundo despliegue CloudFormation se consultaron PostgreSQL 16.13, `db.t3.micro/gp3`, Multi-AZ activo, y dos nodos Redis 7.0.7 `cache.t3.micro` disponibles. "
              "Las versiones declaradas son PostgreSQL 16 y Redis 7.0; estas consultas no sustituyen una comprobación funcional de datos ni prueban las versiones efectivas de las otras corridas. "
              "Evidencia: `logs/intensive-cloudformation-run2-{rds,redis}.json`. El histórico medio declara PostgreSQL 16.15; la comparación entre fechas no mantiene todas las versiones iguales.", "",
              "### Limpieza y costos", "",
              "La auditoría independiente `session-audit-intensive.json` completó sus consultas y registró `cleanup_verified=true`. "
              "Sus inventarios incluyen los recursos del benchmark y consultas adicionales de ElastiCache, NAT, ASG, launch templates, CloudFront y alarmas. "
              "Los logs `logs/audit-intensive-*.log` delimitan el alcance; el estado local conservado no sustituye la confirmación del borrado en AWS.", "",
              f"La suma heurística de los intentos intensivos es {sum(float(r['est_cost_usd'] or 0) for r in rows):.4f} USD. "
              "No es una factura ni un límite máximo: omite, entre otros, HTTP, algunas esperas y limpieza tras fallos. "
              "Los créditos de la sesión histórica no representan el saldo actual ni determinan el costo intensivo. No se cambió el plan de cuenta.", ""]
    (OUT / "INTENSIVO.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Intensive: {len(good)}/{len(rows)} successful; cleanup audited")


if __name__ == "__main__":
    main()
