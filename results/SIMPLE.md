# Benchmark simple: evidencias y limites

**Documento histórico de octubre de 2026.** Sus valores y referencias a líneas describen el CSV y los logs originales, que no estaban presentes en el checkout usado para ejecutar el intensivo en noviembre. El nuevo `results.csv` registra las corridas intensivas y no corresponde a esas referencias históricas. No se reconstruyeron los archivos ausentes. Ver [INTENSIVO.md](INTENSIVO.md) para la ampliación y [HISTORICO_SIMPLE_MEDIO.md](HISTORICO_SIMPLE_MEDIO.md) para la tabla histórica conservada.

## Alcance

Analisis exclusivamente documental de `results.csv`, `logs/simple-*-run1.log`, `logs/simple-*-run1-http.json` y las 16 auditorias `logs/simple-*-remaining-*.log`, existentes en `results/`. No se ejecutaron AWS, despliegues, consultas HTTP ni cambios de infraestructura. No se inspeccionaron ni se reproducen estados, claves, secretos o identificadores de cuenta.

Hay una unica repeticion por herramienta (`run=1`, `tier=simple`, 2026-10-25). Son observaciones individuales, no resultados estadisticos: no permiten estimar dispersion, intervalos de confianza ni superioridad reproducible. No se han consultado plantillas, implementaciones del medidor ni informes de otros escenarios.

## Valores del CSV

Valores literales de las columnas seleccionadas, sin recalcular, corregir ni redondear. Todos los tiempos estan en segundos. Las celdas vacias de `failed_step` corresponden a campos vacios del CSV.

| tool | run | ok | failed_step | init_s | preview_s | deploy_s | noop_preview_s | destroy_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cloudformation | 1 | True | | 1.39 | 33.48 | 63.93 | 2.1 | 64.18 |
| terraform | 1 | True | | 1.96 | 5.53 | 44.85 | 8.6 | 50.8 |
| opentofu | 1 | True | | 2.05 | 6.35 | 46.23 | 12.42 | 50.46 |
| pulumi | 1 | True | | 19.17 | 14.62 | 55.49 | 14.08 | 43.66 |

| tool | loc | resources | state_kind | state_bytes | est_cost_usd |
| --- | --- | --- | --- | --- | --- |
| cloudformation | 105 | 10 | AWS-managed (no local file) | 0 | 0.0007 |
| terraform | 127 | 11 | local terraform.tfstate | 23185 | 0.0006 |
| opentofu | 127 | 11 | local terraform.tfstate | 22457 | 0.0006 |
| pulumi | 108 | 11 | local file backend (.pulumi-state/) | 84593 | 0.0006 |

Fuente: `results.csv:1-5`. `ok=True` describe el resultado registrado por el benchmark, no una certificacion independiente de todas las metricas.

## HTTP: 4/4

| tool | ok | status | error | elapsed_s |
| --- | --- | --- | --- | --- |
| cloudformation | true | 200 | | 17.05 |
| terraform | true | 200 | | 18.52 |
| opentofu | true | 200 | | 16.45 |
| pulumi | true | 200 | | 10.46 |

Fuentes: los cuatro `logs/simple-<tool>-run1-http.json:3-6`. Los cuatro registran HTTP satisfactorio, con `error` vacio. Esto acredita respuesta HTTP en aquella comprobacion, no validacion funcional del juego, disponibilidad sostenida ni rendimiento bajo carga. `elapsed_s` no debe presentarse como latencia de una peticion: estos JSON no desglosan intentos, esperas, reintentos ni tiempo de conexion. Tampoco documentan aqui el instante de inicio respecto del despliegue; no se suma este valor a `deploy_s` para inventar un tiempo total hasta disponibilidad.

## Inicializacion Warm

La inicializacion observada corresponde a un entorno preparado previamente, no a una instalacion en frio. Terraform reutiliza el lock y el proveedor AWS instalado (`simple-terraform-run1.log:2-9`); OpenTofu muestra lo mismo (`simple-opentofu-run1.log:2-10`). Pulumi registra dependencias Python ya satisfechas (`simple-pulumi-run1.log:5-40`), aunque tambien imprime mensajes de creacion de entorno virtual. Esos mensajes no prueban una instalacion limpia.

Ademas, `init_s` no mide el mismo trabajo: CloudFormation valida una plantilla (`simple-cloudformation-run1.log:2-27`), Terraform/OpenTofu inicializan backend y proveedores, y Pulumi registra login al backend local, instalacion, seleccion de stack y configuracion de region (`simple-pulumi-run1.log:2-45`). Los logs no asignan tiempos individuales a esos comandos; no permiten reconstruir de forma independiente que parte exacta integra cada duracion del CSV. La preparacion previa queda fuera de la comparacion de inicializacion publicada.

## No-op Y Destruccion

No se observan cambios inesperados en ninguno de los cuatro no-op:

| tool | Evidencia no-op | Evidencia de destruccion |
| --- | --- | --- |
| cloudformation | `No changes to deploy`, log:41-45 | `delete-stack` y espera de borrado, log:47-49 |
| terraform | `No changes`, log:354-376 | `11 destroyed`, log:754 |
| opentofu | `No changes`, log:364-383 | `11 destroyed`, log:757 |
| pulumi | `12 unchanged`, log:126-133 | `12 deleted`, log:171-176 |

Las referencias de esta tabla corresponden a `logs/simple-<tool>-run1.log`. Los 12 de Pulumi incluyen el recurso de stack; no contradicen los 11 recursos AWS del CSV. Su log tambien advierte que el historial y la configuracion del stack se conservan tras destruir recursos.

El no-op no es una prueba equivalente de deteccion de drift: Terraform/OpenTofu muestran refresh contra AWS, mientras que el comando de Pulumi no incluye `--refresh` y el de CloudFormation no ejecuta deteccion de drift. Ausencia de cambios propuestos no demuestra por si sola ausencia de cambios externos.

## Recursos Y Estado

- CloudFormation declara **10 recursos**, frente a **11 recursos administrados** por Terraform/OpenTofu/Pulumi. No es una discrepancia interna de CloudFormation: la plantilla integra versionado, cifrado y bloqueo publico en el bucket; HCL/Pulumi separan esas opciones, mientras otras diferencias de representacion afectan tambien al total. No interpretar la diferencia como ahorro de un servicio fisico.
- Terraform/OpenTofu: sus planes y resultados de apply enumeran 11 recursos administrados; las lecturas de datos no son recursos creados (`simple-terraform-run1.log:314,347`; `simple-opentofu-run1.log:324,357`).
- Pulumi: el CSV registra 11; el log cuenta 12 incluyendo `pulumi:pulumi:Stack` (`simple-pulumi-run1.log:52-71,120-121`). Mezclar ambos criterios produciria una diferencia artificial.
- Estado Pulumi: la fuente declarada de **84593 bytes** es el **backend local `.pulumi-state/`**, coherente con el login `file://` del log:2-3. No es un export de estado ni una medicion de Pulumi Cloud. Las evidencias no detallan que archivos, historiales o copias entran en el total ni el momento de muestreo; no se atribuye el total exclusivamente al checkpoint activo.
- Estado Terraform/OpenTofu: el CSV identifica un archivo local `terraform.tfstate`. Compararlo directamente con un backend/directorio Pulumi de alcance no documentado no mide exclusivamente la eficiencia del formato de estado.
- Estado CloudFormation: **0 bytes locales no significa estado remoto de tamano cero**. El estado esta gestionado por AWS y su tamano no esta medido aqui.

## Limpieza Auditada

Las 16 auditorias `simple-<tool>-remaining-{instances,vpcs,stacks,databases}.log` devuelven colecciones vacias: `Reservations`, `Vpcs`, stacks no borrados e instancias RDS, respectivamente. Esto es coherente con las destrucciones registradas, dentro del alcance de esas consultas.

Limite concreto: consultan `us-east-1` con filtros de nombre/etiqueta `iacbench-*`; la consulta EC2 excluye instancias terminadas y la de stacks excluye `DELETE_COMPLETE`. No auditan buckets S3, versiones/objetos, volumenes EBS, snapshots u otros recursos, ni otras regiones o recursos sin esas etiquetas. No autorizan a concluir limpieza exhaustiva de la cuenta ni costo residual cero. Son evidencias historicas, no una comprobacion del estado actual.

## Defectos De Medicion

1. **Muestra insuficiente:** una repeticion por herramienta, sin estimacion de variabilidad; ordenar estos tiempos no establece un ganador estadistico.
2. **Inicializacion no comparable y warm:** validacion remota, init con proveedores reutilizados e instalacion Python ya satisfecha son cargas distintas. No se mide la preparacion completa desde cero.
3. **Preview/deploy con semanticas distintas:** CloudFormation crea un change set y espera su finalizacion (`log:29-39`); Terraform/OpenTofu aplican un plan guardado; Pulumi ejecuta `up --skip-preview`, sin aplicar un artefacto de plan guardado visible. Los tiempos incluyen distinta coordinacion de CLI/servicio, no solo velocidad de provisionamiento.
4. **Trazabilidad temporal incompleta:** los logs de ejecucion no incluyen marcas temporales por comando ni los limites de cada cronometro. Por ejemplo, Pulumi muestra `Duration: 52s`/`41s` frente a `deploy_s=55.49`/`destroy_s=43.66`; no se sustituyen cifras, pues duracion interna y medicion externa pueden tener limites distintos, pero estos limites no estan explicitados en las evidencias.
5. **No-op no uniforme:** un plan con refresh, un preview sin refresh explicito y un change set vacio no ofrecen la misma cobertura de drift. Los resultados son limpios, pero la propiedad comprobada es mas estrecha que identidad completa con AWS.
6. **Conteos y LOC con distinta representacion:** el CSV no contiene por si solo el inventario de fuentes. Las reglas estan en `benchmark/bench.py`: LOC excluye blancos y comentarios, y el recurso stack de Pulumi no integra el total. CFN integra configuraciones que otros proveedores separan; estos conteos no equivalen a servicios fisicos ni complejidad funcional.
7. **Bytes de estado con denominadores distintos:** archivo local frente a backend local y estado remoto no medido. Falta inventario agregado y momento de captura; no hay base para comparar tamanos como eficiencia intrinseca.
8. **HTTP con instrumentacion limitada:** `benchmark/bench.py:verify_http` exige HTTP 200 y el titulo exacto de Pong, con reintentos hasta 300 segundos. El JSON registra el resultado y tiempo agregado, no cada intento ni una prueba interactiva del juego. `deploy_s` por si solo no acredita aplicacion lista.
9. **Limpieza parcial:** los resultados vacios no cubren S3 ni todos los componentes potencialmente facturables; no prueban ausencia total de residuos.
10. **Costos heuristicos, NO reales:** `est_cost_usd` es una estimacion heuristica, no facturacion AWS, gasto observado ni costo neto tras creditos. Las fuentes permitidas no documentan formula, tarifas, ventana facturable ni cobertura de EC2/EBS/IPv4/S3/trafico. La diferencia `0.0007` frente a `0.0006` no demuestra ahorro real.

## Conclusion

El CSV registra cuatro ejecuciones satisfactorias y las evidencias HTTP confirman **4/4 con HTTP 200**. No hay cambios inesperados visibles en los no-op y las auditorias consultadas estan vacias. Los tiempos describen esta unica ejecucion preparada; recursos, LOC, bytes y costos requieren las salvedades anteriores y no sostienen por si solos una clasificacion general de las herramientas.
