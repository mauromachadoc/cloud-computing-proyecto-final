## Intensivo: ejecución real

Actualizado UTC: 2026-11-16T03:02:14+00:00.

Se registraron 5 intentos intensivos secuenciales en AWS us-east-1, de los cuales 4 completaron el ciclo con verificación de Pong y destrucción. Los informes de las ocho corridas simple/medio del 25/10/2026 se conservan como evidencia histórica; su CSV y logs originales no estaban en este checkout y no se reconstruyeron. La exclusión histórica del intensivo fue reemplazada por la solicitud de ejecutarlo. No se ejecutó la etapa 4.

### Mediciones intensivas

Segundos de pared del orquestador; HTTP/HTTPS se mide por separado. «—» indica una etapa sin medición registrada, no cero segundos. Los intentos fallidos quedan fuera de las medianas de éxito.

| Herramienta | Corrida | OK | Init | Preview | Deploy | No-op | Destroy | LOC | Recursos | Estado (B) |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cloudformation | 1 | False | 4.09 | 37.47 | 955.25 | 4.32 | — | 342 | 40 | 0 |
| cloudformation | 2 | True | 3.45 | 37.57 | 954.84 | 4.84 | 496.55 | 342 | 40 | 0 |
| terraform | 1 | True | 5.33 | 8.58 | 953.2 | 14.07 | 409.01 | 356 | 41 | 86055 |
| opentofu | 1 | True | 3.66 | 8.98 | 952.36 | 13.85 | 452.27 | 356 | 41 | 84074 |
| pulumi | 1 | True | 30.49 | 25.72 | 908.19 | 19.17 | 867.48 | 131 | 41 | 339802 |

LOC depende del formato y no mide legibilidad ni modularidad. Los recursos son unidades lógicas de cada proveedor, no un conteo homogéneo de servicios AWS. Los 0 B de CloudFormation significan estado administrado por AWS; HCL mide un archivo y Pulumi el directorio completo de su backend. Sus bytes no prueban eficiencia relativa.

### Verificación y fallos

- cloudformation, corrida 1: falló `http_verification`. Ver `logs/intensive-cloudformation-run1.log`; no se interpreta como ciclo exitoso.
  El proceso inicial había cargado el verificador que solo admitía HTTP antes de aplicar la corrección HTTPS. El rechazo no prueba indisponibilidad del sitio. La corrida se conserva como fallida; el reintento usa código corregido y otro número de log. La limpieza del intento inicial no tenía cronómetro registrado en el CSV.
- cloudformation, corrida 2: HTTPS 200 y título de Pong; comprobación en 0.75 s, fuera de deploy.
- terraform, corrida 1: HTTPS 200 y título de Pong; comprobación en 0.66 s, fuera de deploy.
- opentofu, corrida 1: HTTPS 200 y título de Pong; comprobación en 0.84 s, fuera de deploy.
- pulumi, corrida 1: HTTPS 200 y título de Pong; comprobación en 5.84 s, fuera de deploy.

### Comparación descriptiva

- cloudformation: deploy intensivo 954.84 s (2.56 veces el medio); destroy 496.55 s (0.94 veces el medio).
- terraform: deploy intensivo 953.20 s (2.70 veces el medio); destroy 409.01 s (0.87 veces el medio).
- opentofu: deploy intensivo 952.36 s (2.61 veces el medio); destroy 452.27 s (0.97 veces el medio).
- pulumi: deploy intensivo 908.19 s (2.52 veces el medio); destroy 867.48 s (1.48 veces el medio).

Duración de creación por eventos CloudFormation, segundo intento (primer CREATE_IN_PROGRESS a CREATE_COMPLETE):

| Recurso lógico | Segundos |
|---|---:|
| Database | 888.06 |
| Redis | 425.61 |
| Alb | 125.44 |
| CloudFrontDistribution | 154.06 |
| AutoScalingGroup | 15.79 |

RDS fue la última dependencia en completar su creación en este intento. Las operaciones se solapan y no deben sumarse; estos eventos no aíslan el overhead del motor. La creación del ASG no equivale a readiness HTTP de sus instancias. Fuente: `logs/intensive-cloudformation-run2-events.json`.

La referencia medio proviene de la tabla histórica de `RESULTADOS_REALES.md`; el intensivo proviene del CSV nuevo. Son observaciones de ejecuciones individuales, en fechas distintas y con servicios diferentes: no estiman dispersión ni permiten generalizar un ranking. El intensivo agrega NAT, EC2/ASG, RDS Multi-AZ, Redis con réplica, CloudFront y alarmas. No se midió carga intensiva de usuarios: «intensivo» designa la complejidad de infraestructura. Pong no consume RDS ni Redis; HTTPS no prueba failover, autoescalado, caché ni disponibilidad sostenida.

### Preparación y trazabilidad

- Se corrigió el bloque HCL anidado `restrictions/geo_restriction` en Terraform y OpenTofu; ambos pasaron init/validate.
- CLI: Terraform 1.16.6, OpenTofu 1.13.1, Pulumi 3.272.0; orquestador Python 3.12.10. Proveedor AWS HCL 5.100.0 y Pulumi AWS 6.83.4. Ver `logs/intensive-version-*.log` y los logs de init/install.
- El verificador ahora acepta HTTPS para CloudFront. Se agregó una prueba de regresión y `--start-run` para conservar logs de reintentos.
- `intensive-results.csv` conserva las mediciones versionables del CSV original, omitiendo solo el identificador de cuenta. Los logs y auditorías JSON quedan locales según `.gitignore`.
- Ver `pulumi-intensive-summary.json` y `pulumi-intensive-dependencies.log` para preparación y versiones de Pulumi.
- Init intensivo HCL/Pulumi reutiliza la preparación previa; no mide instalación desde cero.

En el segundo despliegue CloudFormation se consultaron PostgreSQL 16.13, `db.t3.micro/gp3`, Multi-AZ activo, y dos nodos Redis 7.0.7 `cache.t3.micro` disponibles. Las versiones declaradas son PostgreSQL 16 y Redis 7.0; estas consultas no sustituyen una comprobación funcional de datos ni prueban las versiones efectivas de las otras corridas. Evidencia: `logs/intensive-cloudformation-run2-{rds,redis}.json`. El histórico medio declara PostgreSQL 16.15; la comparación entre fechas no mantiene todas las versiones iguales.

### Limpieza y costos

La auditoría independiente `session-audit-intensive.json` completó sus consultas y registró `cleanup_verified=true`. Sus inventarios incluyen los recursos del benchmark y consultas adicionales de ElastiCache, NAT, ASG, launch templates, CloudFront y alarmas. Los logs `logs/audit-intensive-*.log` delimitan el alcance; el estado local conservado no sustituye la confirmación del borrado en AWS.

La suma heurística de los intentos intensivos es 0.9730 USD. No es una factura ni un límite máximo: omite, entre otros, HTTP, algunas esperas y limpieza tras fallos. Los créditos de la sesión histórica no representan el saldo actual ni determinan el costo intensivo. No se cambió el plan de cuenta.
