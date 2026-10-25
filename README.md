# iacbench — CloudFormation vs Terraform vs OpenTofu vs Pulumi

Proyecto Final Cloud Computing (UCU). Comparación de cuatro herramientas IaC ejecutando el mismo juego **Pong** en AWS `us-east-1`, con tres niveles de infraestructura y una etapa experimental. Texto/documentación en español; código/comentarios en inglés.

## Estado del proyecto

| Etapa | Qué incluye | Estado de implementación |
|---|---|---|
| 1 — Simple | VPC, EC2, S3; las cuatro herramientas | Código recibido, sin cambios de arquitectura |
| 2 — Medio | VPC, ALB, ECS Fargate, RDS single-AZ | Código generado en las cuatro herramientas |
| 3 — Intensivo | Tres capas multi-AZ, ALB, ASG EC2, RDS Multi-AZ, Redis/ElastiCache, S3, CloudFront, IAM, CloudWatch | Código generado en las cuatro herramientas |
| 4 — Experimentos | Fallo deliberado/rollback, pérdida controlada de estado local, modularidad, cifrado de estado OpenTofu | Código/guías generados en `experiments/` |

**Actualización del 25 de octubre de 2026:** se desplegaron y destruyeron los niveles
simple y medio con las cuatro herramientas en AWS `us-east-1`, con una corrida por
combinación y comprobación HTTP de Pong. Las ocho corridas fueron correctas; los
resultados y auditorías están en `results/RESULTADOS_REALES.md`, `results/results.csv`
y `results/logs/`. La etapa intensiva quedó excluida por decisión del usuario y los
experimentos de etapa 4 no se ejecutaron realmente. Una corrida por herramienta
no constituye una comparación estadística robusta. Ver `VALIDACION.md`.

## Arquitectura

- **Simple:** una subred pública, una instancia EC2 t3.micro con nginx y Pong y un bucket S3 privado con versión y cifrado.
- **Medio:** dos subredes públicas (ALB + ECS Fargate con IP pública) y dos subredes privadas de datos; PostgreSQL single-AZ. No usa NAT. La tarea descarga Pong al arrancar. La base de datos **no** es utilizada por la app y solo estresa la comparación IaC.
- **Intensivo:** dos AZ y seis subredes (pública, app privada, datos privados por AZ), un NAT Gateway compartido (punto único de fallo/costo reducido), ALB público, ASG 2–4 instancias EC2 en subred privada, PostgreSQL Multi-AZ, Redis con réplica y failover, S3 privado, CloudFront con origen ALB, IAM SSM y alarmas CloudWatch. CloudFront sirve el Pong del ALB; el S3 es **almacenamiento privado independiente**, no es el origen de la distribución. RDS y Redis no son usados por Pong.

**Advertencia de equivalencia:** la topología y parámetros principales coinciden entre las herramientas, pero el conteo de recursos lógicos no es idéntico: ciertos proveedores HCL/Pulumi separan la configuración de S3 en varios recursos, y CloudFormation la integra en uno. Los nombres únicos por herramienta son deliberados para evitar colisiones.

La app es [bocaletto-luca/Pong](https://github.com/bocaletto-luca/Pong), GPL-3.0, fijada al commit `58927a56aef0117aa290898d9b48d0f7ee0918b0`. Se obtiene de GitHub al inicializar el cómputo; el navegador también necesita internet para dependencias CDN. El contenedor ECS usa `nginx:stable-alpine`; es una etiqueta móvil: si es esencial la reproducibilidad exacta entre fechas, fijarla por digest en las cuatro implementaciones antes de medir.

## Estructura

```
benchmark/bench.py          # preflight | run --tier simple/medium/intensive | report
benchmark/failure.py        # etapa 4: fallo/rollback, --execute explícito
benchmark/state_loss.py     # etapa 4: estado oculto y restaurado, --execute explícito
tiers/01-simple/<tool>/
tiers/02-medium/<tool>/
tiers/03-intensive/<tool>/
experiments/failure/<tool>/
experiments/modularity/<tool>/
experiments/state-encryption/opentofu/
experiments/README.md       # protocolos y ejecución de etapa 4
results/                    # CSV, informes, logs; generado al ejecutar
```

`<tool>` = `cloudformation`, `terraform`, `opentofu`, `pulumi`.

## Preparación

Se precisan AWS CLI v2, Terraform >= 1.6, OpenTofu >= 1.6, Pulumi CLI, Python >= 3.10, credenciales con permisos para cada servicio. Ejecutar desde la raíz del repo. Para Pulumi usar entornos Python separados generados por `pulumi install` y el backend local `.pulumi-state/`. Terraform/OpenTofu guardan estado en `terraform.tfstate`; CloudFormation guarda estado en AWS.

```bash
python benchmark/bench.py preflight --profile cuenta-a
python benchmark/bench.py run --tier medium --runs 1 --dry-run
python benchmark/bench.py run --tier intensive --runs 1 --dry-run
```

### Validar antes de cada etapa (sin crear infraestructura)

```bash
cd tiers/02-medium/terraform && terraform init && terraform validate && cd ../../..
cd tiers/02-medium/opentofu && tofu init && tofu validate && cd ../../..
cd tiers/03-intensive/terraform && terraform init && terraform validate && cd ../../..
cd tiers/03-intensive/opentofu && tofu init && tofu validate && cd ../../..

# Repetir en cada tier de Pulumi:
cd tiers/02-medium/pulumi && pulumi install && pulumi preview --stack dev && cd ../../..
# CloudFormation:
aws cloudformation validate-template --template-body file://tiers/02-medium/cloudformation/template.yaml
aws cloudformation validate-template --template-body file://tiers/03-intensive/cloudformation/template.yaml
```

**Nota:** Para `pulumi preview` primero seleccioná/creá la pila y configurá el backend local (`pulumi login file://RUTA_ABSOLUTA/.pulumi-state`, `pulumi stack select dev --create`, `PULUMI_CONFIG_PASSPHRASE=""`). `bench.py` hace esa configuración automáticamente.

Los comandos con `&&` suponen Bash o PowerShell 7; en Windows PowerShell 5.1 ejecutá las líneas por separado.

### Benchmark secuencial recomendado

```bash
python benchmark/bench.py run --tier simple --runs 1 --profile cuenta-a
python benchmark/bench.py run --tier medium --runs 1 --profile cuenta-a
python benchmark/bench.py run --tier intensive --runs 1 --profile cuenta-a
# Cuando cada etapa funcione, aumentar --runs 3 o más.
python benchmark/bench.py report
```

También podés limitar a un proveedor con `--tools terraform` o `--tools cloudformation,pulumi`. Cada ciclo realiza preview → deploy → preview sin cambios → destroy. Registra resultados en `results/results.csv`, agregados en `results/results.md`, y logs por corrida en `results/logs/`. **No ejecuta cuatro despliegues simultáneamente.** Si fallan despliegue o limpieza, interrumpir las próximas corridas y verificar en la consola de AWS que no quedaron recursos cobrando. El script intenta borrar los recursos creados, pero la limpieza no está garantizada en todos los fallos.

La opción `--verify-http` comprueba HTTP 200 y el título de Pong antes de destruir,
con reintentos hasta cinco minutos. Su resultado y duración se guardan en
`results/logs/<tier>-<tool>-run<N>-http.json`, separados del cronómetro de deploy.
Si falla la comprobación, la corrida se marca fallida y se intenta limpiar.
No constituye una prueba interactiva del juego ni verifica RDS, que Pong no utiliza.

### Etapa 4

Leer [experiments/README.md](experiments/README.md) antes de ejecutar. Sus pruebas son **independientes** de los benchmarks, y sus comandos de creación requieren `--execute` o una acción manual explícita.

## Costos y limitaciones

**Cada una de las tres cuentas puede generar cargos.** Antes de una sola corrida: fijar alertas de AWS Budgets, revisar servicios permitidos por el plan y verificar manualmente precios en AWS Pricing Calculator. Los números en `TIER_HOURLY_USD_EST` en el script son **marcadores aproximados**, no precios confirmados, y excluyen recursos remanentes, costes de red, almacenamiento, snapshots y tiempo detenido tras una falla. El nivel intensivo tiene NAT, ALB, RDS Multi-AZ, dos nodos ElastiCache, EC2 y CloudFront: es el de mayor riesgo. Destruirlo enseguida y revisar Billing, EC2, RDS, ElastiCache, CloudFront y VPC. Un NAT compartido reduce costes, pero impide HA completa en el camino de salida. Si el plan AWS Free bloquea recursos, no cambiar a Paid sin autorizarlo primero.

## Interpretación de métricas

- Tiempo: CloudFormation cronometrado con change set; HCL con `plan` y `apply`; Pulumi con `preview`/`up`. En ECS configuramos espera de estado estable en HCL/Pulumi. Aun así no son perfectamente homogéneos ni constituyen por sí solos una prueba de disponibilidad HTTP.
- LOC: líneas no vacías y no comentarios, según `bench.py`; incluye `Pulumi.yaml`/`requirements.txt`; comparar también legibilidad/abstracción, no solo tamaño.
- Estado: el tamaño `0` de CloudFormation significa **estado administrado por AWS**, no que no haya estado; Pulumi incluye metadatos de backend en la cuenta de bytes.
- Recursos: cuenta recursos gestionados por la herramienta (distintos modelos de representación), no equivalente a número de servicios AWS.
- Fallos: resultados de la etapa 4 no se suman a medianas de éxito de `bench.py`.

## Qué está excluido

No se generaron las diapositivas de presentación ni el vídeo de respaldo. Se mantiene la propuesta original en `PROPUESTA_FORO.md`. No incluir CDK (decisión ya tomada en la propuesta).

## Informes

- [Informe consolidado e interpretación](results/RESULTADOS_REALES.md): mediciones, lectura de resultados y recomendaciones para el caso probado.
- [Resumen Ejecutivo en PDF](results/RESUMEN_EJECUTIVO.pdf): tres páginas A4 con marco teórico, comparativa, arquitectura, resultados y referencias.
- [Resumen Ejecutivo editable](results/RESUMEN_EJECUTIVO.md): fuente Markdown del documento.

`python results/summarize_aws.py` incorpora la interpretación de
`results/INTERPRETACION.md` al regenerar el informe, sin llamar a AWS.
`results/render_summary.py` genera HTML/PDF desde el resumen, verifica las ocho
filas contra el CSV y comprueba las tres páginas. Requiere las dependencias de
`results/document-requirements.txt` y fuentes Segoe UI/Consolas de Windows.
