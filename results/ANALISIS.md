# Analisis de los benchmarks

## Estado Actual

El histórico documenta ocho ciclos simple/medio de octubre. En noviembre se
completaron cuatro ciclos intensivos en AWS us-east-1, uno por herramienta,
con HTTPS 200, título de Pong, no-op sin cambios y destroy correcto. Se conserva
un quinto intento intensivo fallido de CloudFormation por el verificador anterior;
el reintento con soporte HTTPS fue correcto. La etapa 4 no se ejecutó.

Deploy intensivo: CloudFormation 954,84 s; Terraform 953,20 s; OpenTofu 952,36 s;
Pulumi 908,19 s. Destroy: 496,55; 409,01; 452,27 y 867,48 s, respectivamente.
Una observación exitosa por combinación no permite estimar variabilidad.
El análisis completo y las comparaciones están en [INTENSIVO.md](INTENSIVO.md).

El informe consolidado es [RESULTADOS_REALES.md](RESULTADOS_REALES.md). Las
mediciones intensivas versionables están en [intensive-results.csv](intensive-results.csv),
el CSV local original en `results.csv` y su tabla agregada en
[results.md](results.md). Los logs y la auditoria final se conservan en `logs/`
y `session-audit-intensive.json`; el resumen versionable es
[AUDITORIA_INTENSIVO.md](AUDITORIA_INTENSIVO.md). La auditoría final completó
sus consultas sin remanentes en los inventarios revisados. Las fuentes primarias
de octubre no estaban presentes; su tabla se conserva en
[HISTORICO_SIMPLE_MEDIO.md](HISTORICO_SIMPLE_MEDIO.md).

## Funcionamiento

`benchmark/bench.py` ejecuta secuencialmente cada herramienta. El ciclo mide
setup, preview, deploy y preview sin cambios; lee recursos y estado y mide destroy.
Setup se mide solo en la primera repeticion solicitada por herramienta, incluso con `--start-run 2`. `--verify-http`
comprueba el titulo de Pong y HTTP 200 por HTTP/HTTPS antes de destruir, con tiempo registrado
por separado. Los fallos HTTP marcan la corrida fallida y activan la limpieza.

CloudFormation utiliza change sets; Terraform/OpenTofu aplican un plan guardado;
Pulumi ejecuta preview y up. Los backends son locales excepto CloudFormation.
El CSV contiene mediciones reales, no las simulaciones iniciales.

## Validaciones Y Cambios

- Se instalaron las CLI y proveedores; la preparación intensiva se registra por separado de la histórica.
- Init/validate HCL, cfn-lint simple/medio y previews Pulumi terminaron correctamente.
- PostgreSQL medium se fijo a 16.15, disponible para db.t3.micro/gp3 segun AWS.
- Se corrigio el no-op vacio de CloudFormation y se fijo la region Pulumi.
- Se ordeno ECS despues de adjuntar la politica IAM en HCL/Pulumi.
- Se corrigió el bloque HCL anidado de CloudFront en Terraform/OpenTofu intensivos; ambos pasaron init/validate.
- Se habilitó HTTPS en el verificador y se agregó `--start-run` para preservar los logs de reintentos y medir su setup.
- Las pruebas incluyen regresiones de HTTPS y numeración de reintentos; el chequeo de paquete sin estado se omite en un workspace inicializado.

## Limites De Interpretacion

- Una repeticion es una prueba de funcionamiento; no demuestra superioridad estadistica.
- Init reutiliza dependencias previamente instaladas. No es una medicion de instalacion en frio.
- LOC y recursos dependen de las representaciones, no equivalen a calidad o numero de servicios.
- El estado local de CloudFormation es 0 bytes porque AWS lo administra, no porque no haya estado.
- Pulumi contabiliza el backend completo; HCL mide un archivo de estado.
- Los previews sin cambios no tienen la misma cobertura de drift entre herramientas.
- El costo del CSV es heuristico, excluye partidas y no equivale a facturacion AWS.
- El saldo de creditos puede variar por recompensas y cargos diferidos. No deducir costo real de su diferencia.
- HTTP verifica el documento de Pong, no una sesion de juego, carga sostenida ni conexion a RDS.

## Evidencias Locales Previas

`execution-summary.json` registra la primera fase, cuando solo estaban disponibles
AWS CLI y cfn-lint. Sus bloqueos historicos no representan el estado final: luego
se instalaron las herramientas y se ejecutaron los benchmarks reales.
`run_local.py` ahora escribe `local-results.md` para no sobrescribir resultados
reales. `run_aws.py` ahora también admite ejecutar `intensive` y una auditoría
`audit-intensive` que cubre los servicios adicionales. Su fase `prepare` conserva
el alcance simple/medium; la preparación intensiva se documenta en su propio informe.

No publicar estados, planes ni backups. Los logs contienen cuenta, ARN y
endpoints, y deben revisarse antes de compartirlos publicamente.
