"""Summarize the eight authorized benchmark cycles after the final audit."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def main():
    with (OUT / "results.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    expected = {(tier, tool) for tier in ("simple", "medium")
                for tool in ("cloudformation", "terraform", "opentofu", "pulumi")}
    if len(rows) != 8 or {(r["tier"], r["tool"]) for r in rows} != expected:
        raise RuntimeError("Expected exactly the eight authorized cycles; inspect CSV before summarizing")
    if any(r["ok"] != "True" for r in rows):
        raise RuntimeError("At least one benchmark failed; inspect logs before summarizing")
    audit = json.loads((OUT / "session-audit.json").read_text(encoding="utf-8"))
    if audit["status"] != "completed" or not audit.get("cleanup_verified"):
        raise RuntimeError("Final cleanup audit must complete successfully first")

    def log_json(name):
        text = (OUT / "logs" / name).read_text(encoding="utf-8")
        return json.loads(text.split("\n\n", 1)[1])

    initial = log_json("prepare-credits.log")
    final = log_json("audit-credits.log")
    http = {}
    for row in rows:
        key = f"{row['tier']}-{row['tool']}"
        http[key] = json.loads((OUT / "logs" / f"{key}-run1-http.json").read_text(encoding="utf-8"))
        if not http[key]["ok"]:
            raise RuntimeError(f"HTTP verification failed: {key}")
    initial_credit = initial["accountPlanRemainingCredits"]["amount"]
    final_credit = final["accountPlanRemainingCredits"]["amount"]
    lines = ["# Resultados reales en AWS", "", f"Generado UTC: {datetime.now(timezone.utc).isoformat()}", "",
             "## Alcance", "",
             "Ocho ciclos reales secuenciales en us-east-1: una repeticion por herramienta en simple y medium.",
             "Cada ciclo completo preview, deploy, preview sin cambios, comprobacion HTTP de Pong y destroy.",
             "La etapa intensive quedo expresamente excluida. No se ejecutaron experimentos destructivos de etapa 4.", "",
             "## Tiempos", "", "Segundos medidos por el orquestador. La comprobacion HTTP se cronometra por separado.", "",
             "| Nivel | Herramienta | Init | Preview | Deploy | No-op | Destroy | Recursos | HTTP |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['tier']} | {r['tool']} | {r['init_s']} | {r['preview_s']} | {r['deploy_s']} | {r['noop_preview_s']} | {r['destroy_s']} | {r['resources']} | 200, Pong |")
    lines += ["", "## Creditos Y Costos", "",
              f"- Creditos reportados antes: {initial_credit} USD.",
              f"- Creditos reportados en la auditoria final: {final_credit} USD.",
              f"- Plan final: {final['accountPlanType']} / {final['accountPlanStatus']}; no se cambio el plan.",
              "- El saldo puede actualizarse con retraso; su diferencia no constituye el costo final de estas corridas.",
              "- AWS muestra completada la actividad de crear RDS con recompensa de 20 USD, consistente con el aumento observado. Las actividades no se consultaron al inicio, por lo que no se infiere un costo neto a partir del saldo.",
              f"- Suma heuristica del benchmark: {sum(float(r['est_cost_usd']) for r in rows):.4f} USD. NO es facturacion real ni cota maxima.",
              "- La heuristica excluye tiempos HTTP, ciertas esperas, almacenamiento, trafico y otros cargos. No se consulto una factura consolidada.",
              "- No se encontraron presupuestos configurados al iniciar; no se crearon alertas ni se cambio la configuracion de facturacion.", "",
              "## Limpieza", "",
              "Los ocho destroy completaron. Se conservaron estado local e historial como evidencia, sin usarlos como sustituto del borrado AWS.",
              "La auditoria final esta en session-audit.json y logs/audit-*.log; registra VPC, instancias activas, RDS, stacks, S3, ALB, ECS, roles, snapshots y otros inventarios.",
              "Todos los inventarios de esa auditoria devolvieron colecciones vacias, incluidos volumenes EBS, Elastic IP, target groups y secretos RDS activos.",
              "Las consultas por prefijo solo cubren recursos iacbench; los inventarios account-* muestran tambien recursos no filtrados, sin borrarlos.", "",
              "## Preparacion Y Correcciones", "",
              "- Terraform 1.16.6, OpenTofu 1.13.1, Pulumi CLI/SDK 3.272.0; Python 3.12.10.",
              "- Proveedor AWS de Terraform/OpenTofu 5.100.0; Pulumi AWS 6.83.4.",
              "- Se validaron HCL y plantillas de simple/medium y se ejecutaron previews Pulumi antes de medir.",
              "- PostgreSQL medium se fijo a 16.15 tras verificar disponibilidad para db.t3.micro/gp3.",
              "- CloudFormation acepta correctamente el change set vacio del no-op.",
              "- Pulumi configura explicitamente us-east-1; ECS espera la politica IAM adjunta en HCL/Pulumi.",
              "- Se agrego --verify-http: exige HTTP 200 y el titulo exacto de Pong; ante fallo intenta destruir el despliegue.",
              "- Las pruebas excluyen dependencias generadas. El chequeo de paquete sin estado se omite en un workspace inicializado.", "",
              *(OUT / "INTERPRETACION.md").read_text(encoding="utf-8").splitlines(), "",
              "## Evidencias", "",
              "- results.csv: mediciones reales originales; results.md: tabla generada por bench.py report.",
              "- logs/<nivel>-<herramienta>-run1.log: salida de las CLI.",
              "- logs/<nivel>-<herramienta>-run1-http.json: resultado HTTP antes de destruir.",
              "- session-<nivel>-<herramienta>.json: identidad, creditos, resultado y consultas de limpieza.",
              "- execution-summary.json: verificaciones locales PREVIAS; no confundirlas con las corridas AWS.",
              "- logs/audit-tests.log: pruebas finales. Las lineas FAILED impresas por los mocks de HTTP son esperadas; consultar el resumen unittest.", "",
              "Los logs contienen cuenta, ARN y endpoints. No publicar estados, planes o backups; revisar tambien metadatos antes de compartir logs.", ""]
    (OUT / "RESULTADOS_REALES.md").write_text("\n".join(lines), encoding="utf-8")
    payload = dict(generated=datetime.now(timezone.utc).isoformat(), rows=rows, http=http,
                   initial_credits_usd=initial_credit, final_credits_usd=final_credit,
                   intensive_executed=False, audit_status=audit["status"])
    (OUT / "aws-summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"8/8 cycles and HTTP checks passed. Credits: {initial_credit} -> {final_credit} USD.")
    print("Written results/RESULTADOS_REALES.md and results/aws-summary.json")


if __name__ == "__main__":
    main()
