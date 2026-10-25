# Estado de validación — 25 de octubre de 2026

## Actualización: Ejecuciones Reales

Se completó una corrida de los niveles simple y medio con CloudFormation,
Terraform, OpenTofu y Pulumi: **8/8 correctas**, con HTTP 200 y el título esperado
de Pong antes de destruir. Los ocho destroy terminaron correctamente. La etapa
intensiva quedó expresamente excluida y no se ejecutaron experimentos reales.

Se instalaron Terraform 1.16.6, OpenTofu 1.13.1 y Pulumi 3.272.0. Los niveles
simple/medio pasaron init/validate HCL, cfn-lint y previews Pulumi. Los proveedores
resueltos fueron AWS 5.100.0 en HCL y Pulumi AWS 6.83.4. PostgreSQL del nivel medio
se fijó a 16.15 tras comprobar compatibilidad en us-east-1. Se corrigieron el
no-op de CloudFormation, la región explícita de Pulumi y la dependencia IAM de ECS.

Las pruebas finales registran nueve correctas y una omitida: el chequeo de paquete
sin estado no aplica después de inicializar el workspace. Los artefactos de estado
y entornos virtuales se conservaron y se excluyen de los recorridos de fuentes.

Evidencias: `results/RESULTADOS_REALES.md`, `results/results.csv`,
`results/session-audit.json` y `results/logs/audit-*.log`. Los tiempos de init son
warm por la preparación previa. No se validó interactivamente el juego ni una
conexión a RDS, que la aplicación no usa. Los costos del CSV siguen siendo
heurísticos, no facturación real. El historial siguiente describe el estado
anterior a estas corridas y no debe confundirse con el estado actualizado.

## Verificado localmente (sin AWS)

- El ZIP original incluía solamente `tiers/01-simple`. No se recuperaron archivos de etapas 2 o 3; se regeneraron a partir del resumen y la propuesta originales.
- Las cuatro implementaciones nuevas están presentes para medio e intensivo.
- Las plantillas YAML (CloudFormation y Pulumi) se parsearon con PyYAML, que **no verifica semántica CloudFormation**.
- Todos los programas Python se compilaron sintácticamente (`ast.parse` / `py_compile`), **sin importar/ejecutar `pulumi_aws`**, porque el proveedor no está instalado.
- El benchmark `--dry-run` genera comandos para los cuatro proveedores en los dos niveles nuevos sin errores.
- Los scripts `benchmark/failure.py` hacen dry-run sin AWS y `state_loss.py` muestra correctamente la limitación de CloudFormation.
- Se agregó una prueba estructural `python -m unittest discover -s tests -v` que comprueba inventario, sintaxis básica, CloudFormation/LOC, equivalencia textual HCL y ausencia de archivos de estado.
- Las plantillas de CloudFormation caben por debajo del límite de `--template-body` de 51.200 bytes.

## No verificado

- `cfn-lint`, `aws cloudformation validate-template` en AWS.
- `terraform fmt`, `terraform init && terraform validate`, `tofu fmt`, `tofu init && tofu validate`.
- Instalación y preview de Pulumi con `pulumi_aws` 6.x en Python, ni funcionamiento del backend de ficheros.
- Despliegues y limpiezas reales, condiciones de IAM/cuotas/capacidades del Free plan, aprobaciones de AWS, restricciones de región, estabilidad de la imagen `nginx:stable-alpine` y descargas desde GitHub.
- Medidas reales de latencia/coste. Los números en `bench.py` siguen siendo estimaciones y la muestra no incluye readiness HTTP independiente.

## Orden recomendado de verificación real

1. Verificar AWS CLI y la cuenta actual con `python benchmark/bench.py preflight --profile <nombre>`.
2. Configurar AWS Budgets, estimar los costes actuales y verificar las cuotas de la cuenta.
3. Instalar las herramientas y ejecutar `fmt`, `validate`, `pulumi preview` en cada nivel (ver README).
4. Ejecutar `--runs 1` por etapa y por herramienta. Verificar tanto el resultado HTTP como el cleanup en AWS Billing/Consola.
5. Solo cuando sea estable, hacer `--runs 3` y posteriormente los experimentos de etapa 4.

## Limitaciones metodológicas

- No se compara qué tan útil es la base/caché para Pong, porque no son usadas por la app.
- ALB/ASG/ECS/CloudFront tienen diferentes condiciones de readiness según proveedor.
- CloudFormation usa un motor de control de estado administrado por AWS; `0 B` local es una ausencia de archivo local, no ausencia de estado.
- Terraform/OpenTofu/Pulumi pueden representar un mismo bucket como varios recursos; no comparar recuentos sin normalizar las definiciones.
- El NAT único del nivel intensivo reduce gasto, pero compromete alta disponibilidad de egreso multi-AZ.
- El experimento de fallo comprueba invalidación de una política S3. Los errores anticipados por provider no constituyen rollback de recursos creados: registrar el punto exacto del fallo.

## Fuentes técnicas consultadas

- [AWS CloudFormation DeletionPolicy](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-deletionpolicy.html) — para evitar snapshots residuales de RDS.
- [AWS ElastiCache ReplicationGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-elasticache-replicationgroup.html) — réplica y failover.
- [Terraform aws_ecs_service](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_service) y [Pulumi ECS Service](https://www.pulumi.com/registry/packages/aws%406.x/api-docs/ecs/service/) — `wait_for_steady_state`.
- [OpenTofu State/Plan Encryption](https://opentofu.org/docs/language/state/encryption/) — configuración PBKDF2/AES-GCM del experimento.
