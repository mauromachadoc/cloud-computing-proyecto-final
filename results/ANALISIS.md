# Analisis de los benchmarks

## Estado Actual

Se completaron ocho ciclos reales en AWS us-east-1: una repeticion por herramienta
en los niveles simple y medio. Los ocho despliegues sirvieron el documento Pong
correctamente y los ocho destroy completaron. La etapa intensiva y los
experimentos destructivos de etapa 4 no se ejecutaron.

El informe consolidado es [RESULTADOS_REALES.md](RESULTADOS_REALES.md). Las
mediciones originales estan en [results.csv](results.csv) y su tabla agregada en
[results.md](results.md). Los logs y la auditoria final se conservan en `logs/`
y `session-audit.json`.

## Funcionamiento

`benchmark/bench.py` ejecuta secuencialmente cada herramienta. El ciclo mide
setup, preview, deploy y preview sin cambios; lee recursos y estado y mide destroy.
Setup se mide solo en la primera repeticion por herramienta. `--verify-http`
comprueba el titulo de Pong y HTTP 200 antes de destruir, con tiempo registrado
por separado. Los fallos HTTP marcan la corrida fallida y activan la limpieza.

CloudFormation utiliza change sets; Terraform/OpenTofu aplican un plan guardado;
Pulumi ejecuta preview y up. Los backends son locales excepto CloudFormation.
El CSV contiene mediciones reales, no las simulaciones iniciales.

## Validaciones Y Cambios

- Se instalaron las tres CLI faltantes y sus proveedores para los dos niveles autorizados.
- Init/validate HCL, cfn-lint simple/medio y previews Pulumi terminaron correctamente.
- PostgreSQL medium se fijo a 16.15, disponible para db.t3.micro/gp3 segun AWS.
- Se corrigio el no-op vacio de CloudFormation y se fijo la region Pulumi.
- Se ordeno ECS despues de adjuntar la politica IAM en HCL/Pulumi.
- Las pruebas finales registran nueve correctas y una omitida por ser exclusiva de paquetes sin estado.

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
reales. `run_aws.py` solo admite preparar, auditar o ejecutar simple/medium; no
ofrece una fase intensiva.

No publicar estados, planes ni backups. Los logs contienen cuenta, ARN y
endpoints, y deben revisarse antes de compartirlos publicamente.
