# Resultados reales en AWS

Generado UTC: 2026-10-25T07:42:20.314423+00:00

## Alcance

Ocho ciclos reales secuenciales en us-east-1: una repeticion por herramienta en simple y medium.
Cada ciclo completo preview, deploy, preview sin cambios, comprobacion HTTP de Pong y destroy.
La etapa intensive quedo expresamente excluida. No se ejecutaron experimentos destructivos de etapa 4.

## Tiempos

Segundos medidos por el orquestador. La comprobacion HTTP se cronometra por separado.

| Nivel | Herramienta | Init | Preview | Deploy | No-op | Destroy | Recursos | HTTP |
|---|---|---|---|---|---|---|---|---|
| simple | cloudformation | 1.39 | 33.48 | 63.93 | 2.1 | 64.18 | 10 | 200, Pong |
| simple | terraform | 1.96 | 5.53 | 44.85 | 8.6 | 50.8 | 11 | 200, Pong |
| simple | opentofu | 2.05 | 6.35 | 46.23 | 12.42 | 50.46 | 11 | 200, Pong |
| simple | pulumi | 19.17 | 14.62 | 55.49 | 14.08 | 43.66 | 11 | 200, Pong |
| medium | cloudformation | 3.0 | 36.56 | 373.05 | 3.82 | 528.69 | 23 | 200, Pong |
| medium | terraform | 4.15 | 8.86 | 353.62 | 12.91 | 468.3 | 22 | 200, Pong |
| medium | opentofu | 3.26 | 8.48 | 364.27 | 14.14 | 465.28 | 22 | 200, Pong |
| medium | pulumi | 20.95 | 13.28 | 360.7 | 21.78 | 586.4 | 22 | 200, Pong |

## Creditos Y Costos

- Creditos reportados antes: 118.8 USD.
- Creditos reportados en la auditoria final: 138.8 USD.
- Plan final: FREE / ACTIVE; no se cambio el plan.
- El saldo puede actualizarse con retraso; su diferencia no constituye el costo final de estas corridas.
- AWS muestra completada la actividad de crear RDS con recompensa de 20 USD, consistente con el aumento observado. Las actividades no se consultaron al inicio, por lo que no se infiere un costo neto a partir del saldo.
- Suma heuristica del benchmark: 0.1506 USD. NO es facturacion real ni cota maxima.
- La heuristica excluye tiempos HTTP, ciertas esperas, almacenamiento, trafico y otros cargos. No se consulto una factura consolidada.
- No se encontraron presupuestos configurados al iniciar; no se crearon alertas ni se cambio la configuracion de facturacion.

## Limpieza

Los ocho destroy completaron. Se conservaron estado local e historial como evidencia, sin usarlos como sustituto del borrado AWS.
La auditoria final esta en session-audit.json y logs/audit-*.log; registra VPC, instancias activas, RDS, stacks, S3, ALB, ECS, roles, snapshots y otros inventarios.
Todos los inventarios de esa auditoria devolvieron colecciones vacias, incluidos volumenes EBS, Elastic IP, target groups y secretos RDS activos.
Las consultas por prefijo solo cubren recursos iacbench; los inventarios account-* muestran tambien recursos no filtrados, sin borrarlos.

## Preparacion Y Correcciones

- Terraform 1.16.6, OpenTofu 1.13.1, Pulumi CLI/SDK 3.272.0; Python 3.12.10.
- Proveedor AWS de Terraform/OpenTofu 5.100.0; Pulumi AWS 6.83.4.
- Se validaron HCL y plantillas de simple/medium y se ejecutaron previews Pulumi antes de medir.
- PostgreSQL medium se fijo a 16.15 tras verificar disponibilidad para db.t3.micro/gp3.
- CloudFormation acepta correctamente el change set vacio del no-op.
- Pulumi configura explicitamente us-east-1; ECS espera la politica IAM adjunta en HCL/Pulumi.
- Se agrego --verify-http: exige HTTP 200 y el titulo exacto de Pong; ante fallo intenta destruir el despliegue.
- Las pruebas excluyen dependencias generadas. El chequeo de paquete sin estado se omite en un workspace inicializado.

## Interpretación De Resultados

### Lectura General

El caso de estudio demuestra que las cuatro implementaciones pudieron gestionar el ciclo completo de la aplicación en los niveles simple y medio: **8 de 8 corridas correctas**, sin cambios propuestos en el segundo preview, con HTTP 200 y el título esperado de Pong antes del borrado. La auditoría final no encontró remanentes en los inventarios consultados. Esto valida la viabilidad de las implementaciones probadas; no demuestra disponibilidad sostenida, funcionamiento interactivo del juego, recuperación ante fallos o comportamiento en producción.

Aunque existe una sola repetición por combinación, sus resultados permiten una comparación descriptiva concreta. En el nivel simple, Terraform registró el menor tiempo de despliegue (44,85 s), seguido de OpenTofu (46,23 s), Pulumi (55,49 s) y CloudFormation (63,93 s). Pulumi tuvo la destrucción más corta (43,66 s). Por tanto, incluso dentro de este caso, la herramienta con menor tiempo de creación no es la de menor tiempo de eliminación: la conveniencia depende de la operación que se priorice.

### Efecto De La Complejidad

En el nivel medio, los despliegues convergieron en torno a seis minutos: Terraform 353,62 s, Pulumi 360,70 s, OpenTofu 364,27 s y CloudFormation 373,05 s. La separación entre los extremos fue de **19,43 s, equivalente al 5,49 % del menor tiempo**. Terraform conservó el menor deploy observado, pero la proximidad de los valores no justifica atribuirle una ventaja general de rendimiento.

| Herramienta | Deploy medio / simple | Destroy medio / simple | LOC simple → medio |
|---|---:|---:|---:|
| CloudFormation | 5,84 veces | 8,24 veces | 105 → 199 |
| Terraform | 7,88 veces | 9,22 veces | 127 → 205 |
| OpenTofu | 7,88 veces | 9,22 veces | 127 → 205 |
| Pulumi | 6,50 veces | 13,43 veces | 108 → 79 |

Los factores son cocientes de las observaciones, no leyes de escalabilidad. Al pasar de simple a medio no solo aumentó el inventario: cambió el tipo de cómputo y se incorporaron ALB, ECS y RDS. Por ello, el aumento de tiempo no debe interpretarse como crecimiento lineal con la cantidad de recursos o con las líneas de código.

Los logs de creación del nivel medio sitúan RDS en **321 s con Terraform, 332 s con OpenTofu y 321 s con Pulumi**; el ALB requirió 134, 134 y 144 s, respectivamente. El servicio ECS se creó después del balanceador y esperó su estabilización. RDS terminó más tarde que esas ramas y fue una espera determinante. Estas operaciones se solapan: **no corresponde sumar sus duraciones como si fueran secuenciales**. El patrón es compatible con un ciclo dominado por el aprovisionamiento de AWS y sus dependencias, no por el tamaño del código. No se aisló el overhead del motor IaC; también intervienen versiones de proveedores, sondeo y variación del servicio. El log de CloudFormation registra esperas de stack, pero no permite reconstruir por sí solo sus tiempos por recurso.

### Destrucción Y Operación

La destrucción del nivel medio osciló entre **465,28 s con OpenTofu y 586,40 s con Pulumi**: una diferencia de 121,12 s, o 26,03 % respecto del menor valor. Terraform quedó a solo 3,02 s de OpenTofu. En Terraform y OpenTofu, eliminar ECS tomó unos 427 s, frente a 113 s de RDS; la espera del servicio fue relevante para el final del ciclo. En Pulumi, ECS tomó unos 435 s y el log sitúa el inicio del borrado de ALB y RDS después de su finalización, lo que contribuyó al mayor tiempo observado. Esta secuencia no prueba por sí sola que Pulumi sea intrínsecamente más lento.

Para entornos efímeros, **destroy merece la misma atención que deploy**: el nivel medio tardó más en eliminarse que en crearse con las cuatro herramientas. Un pipeline debe reservar tiempo para el drenaje y liberación de servicios, conservar el estado hasta confirmar el borrado y auditar los recursos después. Un error o una interrupción del cliente no equivale a haber detenido los cargos.

### Preview, Código Y Estado

Los previews iniciales de Terraform y OpenTofu fueron los más breves: 5,53/6,35 s en simple y 8,86/8,48 s en medio. CloudFormation requirió 33,48/36,56 s porque el procedimiento crea un change set remoto y espera su estado; Pulumi necesitó 14,62/13,28 s. Los init tampoco son equivalentes: validación de plantilla, inicialización de proveedores o login, instalación Python y selección de stack. Todos se midieron con preparación previa, por lo que no representan instalaciones desde cero.

Los ocho no-op fueron limpios, pero eso no constituye una prueba uniforme de drift: los planes HCL actualizan información del proveedor, Pulumi no incluyó `--refresh` y CloudFormation no ejecutó detección explícita de drift. Los tiempos describen esos comandos, no una comparación de la misma cobertura de verificación.

En el nivel medio, Pulumi fue la implementación más compacta según LOC: **79 líneas frente a 199 de CloudFormation y 205 de HCL**, un 61,46 % menos que Terraform/OpenTofu. Incluso disminuyó frente a sus 108 líneas del nivel simple. Esto refleja el estilo de esta implementación, con expresiones, comprensiones y múltiples argumentos por línea; no prueba mayor modularidad, legibilidad ni menor esfuerzo de mantenimiento. Los experimentos específicos de modularidad no se ejecutaron.

Los recursos lógicos tampoco son unidades físicas homogéneas: CloudFormation integra opciones que HCL/Pulumi pueden separar. El nivel medio registró 23 recursos en CloudFormation y 22 en las demás herramientas sin que ello implique servicios adicionales equivalentes. El estado medio ocupó 45.666 B en Terraform, 44.711 B en OpenTofu y 193.481 B en el backend local Pulumi; este último incluye un directorio completo, no un único checkpoint comparable. Los 0 B locales de CloudFormation significan **estado administrado por AWS**, no ausencia de estado. No se midieron recuperación, locking, colaboración ni seguridad del backend.

### Conclusiones Para La Elección

**Terraform y OpenTofu** presentaron un comportamiento cercano con configuraciones HCL principales equivalentes y proveedor AWS 5.100.0. En este caso, son opciones razonables cuando se priorizan un flujo declarativo explícito y planes breves. Los tiempos no permiten elegir entre ambos de manera concluyente; la gobernanza, el ecosistema y los requisitos de estado necesitan una evaluación adicional.

**Pulumi** resultó atractivo por la concisión de Python y logró un deploy medio comparable al de HCL, a cambio de preparar un entorno Python y gestionar su backend. Su mayor destroy medio observado debe considerarse al diseñar pipelines efímeros, sin extrapolarlo a cualquier aplicación. La reutilización mediante componentes es una capacidad teórica, no una ventaja medida en esta corrida.

**CloudFormation** permitió gestionar la infraestructura como stacks y sin mantener un archivo de estado local. Su preview inicial fue el más largo del procedimiento utilizado, mientras su no-op fue breve. Puede ser conveniente para un equipo centrado en AWS que prefiera esa integración; no se probó que tenga mejor rollback o menor complejidad operativa total.

La conclusión ejecutiva es que **las cuatro herramientas fueron funcionalmente viables y, al aumentar la complejidad, las esperas de los servicios pasaron a dominar los tiempos observados**. Para este proyecto, el lenguaje del equipo, la operación del estado, la claridad del plan y el procedimiento de limpieza pesan tanto como diferencias de segundos. El nivel intensivo y los experimentos de fallo, recuperación y modularidad siguen pendientes; estas mediciones no permiten anticipar sus resultados. El aumento de créditos de 118,80 a 138,80 USD es consistente con una recompensa RDS de 20 USD, no con un costo negativo: el costo facturado de la prueba no quedó determinado.

Fuente empírica: `results.csv`, `benchmark/bench.py` y `logs/medium-{terraform,opentofu,pulumi,cloudformation}-run1.log`. Los tiempos por recurso son los informados por las CLI; no representan una instrumentación independiente del servicio AWS. El [Resumen Ejecutivo](RESUMEN_EJECUTIVO.md), también disponible en [PDF de tres páginas](RESUMEN_EJECUTIVO.pdf), incorpora marco teórico, arquitectura y bibliografía oficial.

## Evidencias

- results.csv: mediciones reales originales; results.md: tabla generada por bench.py report.
- logs/<nivel>-<herramienta>-run1.log: salida de las CLI.
- logs/<nivel>-<herramienta>-run1-http.json: resultado HTTP antes de destruir.
- session-<nivel>-<herramienta>.json: identidad, creditos, resultado y consultas de limpieza.
- execution-summary.json: verificaciones locales PREVIAS; no confundirlas con las corridas AWS.
- logs/audit-tests.log: pruebas finales. Las lineas FAILED impresas por los mocks de HTTP son esperadas; consultar el resumen unittest.

Los logs contienen cuenta, ARN y endpoints. No publicar estados, planes o backups; revisar tambien metadatos antes de compartir logs.
