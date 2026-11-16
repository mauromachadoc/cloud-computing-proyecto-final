# Resumen Ejecutivo

## IaC en AWS: CloudFormation, Terraform, OpenTofu y Pulumi

**Proyecto Final de Cloud Computing · Universidad Católica del Uruguay**  
**Equipo:** Joaquín Ballara, Facundo Dutra y Mauro Machado. **Actualización:** noviembre de 2026.

### Objetivo Y Hallazgo Principal

Se comparan cuatro herramientas de infraestructura como código (IaC) al desplegar Pong en AWS `us-east-1`, con tres niveles de complejidad. Las ocho corridas simple/medio de octubre se amplían con cuatro ciclos intensivos completos y un intento fallido conservado. El nivel medio registró deploys de 353,62 a 373,05 s. En el segundo intento intensivo de CloudFormation, RDS necesitó 888,06 s y fue la última dependencia en terminar: las esperas de AWS son relevantes para interpretar el cronómetro. **No se identifica un ganador universal** [9].

### Marco Teórico Y Comparativa

IaC expresa la infraestructura en archivos reproducibles y versionables. El modelo declarativo describe el estado deseado; un motor resuelve dependencias y solicita cambios mediante las API del proveedor. El plan o preview permite inspeccionar operaciones antes de ejecutarlas. El estado relaciona las declaraciones con los recursos existentes; su custodia es una responsabilidad operativa, no solo un detalle de almacenamiento [1-4, 6-7].

| Herramienta | Modelo utilizado | Diferencial y responsabilidad |
|---|---|---|
| CloudFormation | Plantillas YAML, stacks y change sets | Integración nativa AWS y estado administrado por el servicio [1]. |
| Terraform | HCL declarativo, plan y apply | Proveedores para múltiples plataformas; requiere gestionar backend y estado [2, 6]. |
| OpenTofu | HCL declarativo, plan y apply | Cifrado nativo de estado y planes como capacidad diferencial; no se activó en esta prueba [3, 10]. |
| Pulumi | Python que declara recursos y dependencias | Permite abstracciones del lenguaje; agrega SDK, entorno Python y elección de backend [4, 7]. |

Usar Python no convierte el despliegue en una secuencia manual de scripts: el motor Pulumi conserva la resolución de dependencias y el estado deseado. Asimismo, un preview sin cambios es una señal de estabilidad de la configuración, pero no equivale a una auditoría uniforme de drift entre herramientas.

### Arquitectura Del Caso

**Simple:** VPC, una subred pública, Internet Gateway, rutas, grupo de seguridad y EC2 `t3.micro` con Amazon Linux 2023 y nginx. Un bucket S3 privado, versionado y cifrado es independiente del sitio. Pong se descarga al arrancar desde un commit fijo GPL-3.0 [8-9].

**Medio:** VPC en dos zonas de disponibilidad, dos subredes públicas para ALB y ECS Fargate, y dos privadas para datos. Una tarea de 0,25 vCPU/0,5 GiB recibe tráfico del ALB y utiliza IP pública para salir a Internet, sin NAT Gateway. PostgreSQL 16.15 corre en RDS `db.t3.micro` single-AZ. Fargate evita administrar servidores del contenedor [5].

**Intensivo:** seis subredes en dos AZ, NAT compartido, ALB y ASG de 2-4 EC2 privadas, RDS Multi-AZ, Redis con réplica, S3 privado, CloudFront, IAM y alarmas. El recorrido público es `CloudFront → ALB → EC2/Pong`; S3 es independiente del origen. Un único NAT limita la disponibilidad del egreso [9].

**RDS y Redis no son consumidos por Pong**: aumentan la complejidad de infraestructura, no su funcionalidad. «Intensivo» no significa una prueba de carga de usuarios; verificar HTTPS tampoco prueba failover ni autoescalado.

<!-- pagebreak -->

### Método Y Resultados

El orquestador ejecutó secuencialmente `init → preview → deploy → preview sin cambios → verificación HTTP → destroy`. Midió tiempo de pared, líneas efectivas de código (LOC), recursos y huella del estado. HTTP exigió código 200 y el título de Pong antes de destruir; se cronometró por separado. Los proveedores y dependencias se instalaron previamente: init es una medición **warm**, no una instalación desde cero [9].

Las ocho filas de octubre se conservan de los informes versionados: sus CSV y logs originales no estaban en este checkout. Las filas intensivas provienen del CSV nuevo. El primer intento de CloudFormation rechazó HTTPS por un defecto del verificador; se conserva como fallido y se excluye de esta tabla de éxitos. El reintento corrigió el verificador y sirvió Pong por HTTPS [9].

| Nivel | Herramienta | Preview (s) | Deploy (s) | Destroy (s) | LOC |
|---|---|---:|---:|---:|---:|
| Simple | CloudFormation | 33,48 | 63,93 | 64,18 | 105 |
| Simple | Terraform | 5,53 | 44,85 | 50,80 | 127 |
| Simple | OpenTofu | 6,35 | 46,23 | 50,46 | 127 |
| Simple | Pulumi | 14,62 | 55,49 | 43,66 | 108 |
| Medio | CloudFormation | 36,56 | 373,05 | 528,69 | 199 |
| Medio | Terraform | 8,86 | 353,62 | 468,30 | 205 |
| Medio | OpenTofu | 8,48 | 364,27 | 465,28 | 205 |
| Medio | Pulumi | 13,28 | 360,70 | 586,40 | 79 |
| Intensivo | CloudFormation | 37,57 | 954,84 | 496,55 | 342 |
| Intensivo | Terraform | 8,58 | 953,20 | 409,01 | 356 |
| Intensivo | OpenTofu | 8,98 | 952,36 | 452,27 | 356 |
| Intensivo | Pulumi | 25,72 | 908,19 | 867,48 | 131 |

**Interpretación temporal.** En el histórico, Terraform tuvo el menor deploy simple/medio; Pulumi eliminó antes el simple y OpenTofu el medio. En intensivo, deploy varió entre 908,19 y 954,84 s, y destroy entre 409,01 y 867,48 s. Pulumi tuvo el menor deploy intensivo y el mayor destroy; Terraform tuvo el menor destroy. **No hay un ganador en todas las operaciones.** Una observación exitosa por combinación no permite estimar variabilidad ni generalizar el ranking [9].

En el histórico medio, RDS necesitó 321-332 s; en el intensivo CloudFormation, 888,06 s. Son ramas parcialmente paralelas y sus tiempos no se suman. En medio, eliminar ECS tomó 427-435 s. Cambian los servicios y dependencias: no se aisló el overhead del motor ni corresponde atribuirle toda diferencia [9].

**Código y estado.** Pulumi usa 79 LOC frente a 205 de HCL en medio, y 131 frente a 356 en intensivo. La concisión depende del estilo y formato; no prueba modularidad ni facilidad de mantenimiento. Los recursos lógicos tampoco son unidades homogéneas entre proveedores.

HCL mide un archivo de estado y Pulumi todo un directorio de backend: **no son medidas equivalentes de eficiencia**. CloudFormation registra 0 B locales porque AWS administra su estado. No se probaron pérdida de estado, colaboración ni recuperación [6-7, 9].

<!-- pagebreak -->

### Conclusión Y Recomendación

Las cuatro herramientas resultaron viables para las tres arquitecturas. **Terraform/OpenTofu** son candidatos sólidos si el equipo prioriza HCL y planes explícitos: sus tiempos fueron cercanos y no justifican elegir uno únicamente por rendimiento. **Pulumi** es atractivo para un equipo afín a Python y produjo menos texto, aunque exige gestionar sus dependencias y considerar el destroy observado en pipelines efímeros. **CloudFormation** resulta coherente con una estrategia centrada en AWS y estado administrado, aceptando el procedimiento de change sets. Estas recomendaciones combinan resultados observados y capacidades documentadas, no ventajas operativas exhaustivamente probadas [1-4, 9].

La decisión debe priorizar conocimiento del equipo, claridad del código, operación del estado y limpieza, además del cronómetro. En este caso, **el nivel medio tardó más en destruirse que en crearse con las cuatro herramientas**. Por ello, un pipeline debe reservar tiempo para liberar servicios y comprobar remanentes antes de iniciar otra corrida.

### Alcance, Seguridad Y Costos

La muestra no permite estimar variabilidad ni generalizar un ranking. Los no-op no tuvieron igual cobertura de drift; los proveedores fueron AWS 5.100.0 en HCL y 6.83.4 en Pulumi. El SDK Pulumi intensivo fue 3.276.0, frente a 3.272.0 en octubre; las fechas y algunas versiones de servicio también difieren. La imagen ECS es mutable y Pong/CDN introduce dependencias externas. No se ejecutaron los experimentos de rollback, pérdida de estado y modularidad [9].

El histórico de octubre reporta inventarios vacíos y créditos de 118,80 a 138,80 USD, consistentes con una recompensa RDS de 20 USD. Su costo heurístico fue 0,1506 USD: no es una factura ni describe el gasto intensivo. La extensión tiene su propia auditoría y estimación en `INTENSIVO.md` y `AUDITORIA_INTENSIVO.md`. Los créditos pueden actualizarse con retraso; no se usó su diferencia para inferir costos ni se cambió el plan de cuenta [9].

### Referencias Bibliográficas

Fuentes web consultadas el 25 de octubre de 2026; documentación sin fecha de publicación indicada.

[1] Amazon Web Services. *What is CloudFormation?* [Guía del servicio](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html).

[2] HashiCorp. *What is Terraform?* [Introducción oficial](https://developer.hashicorp.com/terraform/intro).

[3] OpenTofu. *What is OpenTofu?* [Introducción oficial](https://opentofu.org/docs/intro/).

[4] Pulumi. *Concepts*. [Modelo y motor de despliegue](https://www.pulumi.com/docs/iac/concepts/).

[5] Amazon Web Services. *Architect for AWS Fargate for Amazon ECS*. [Guía de arquitectura](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html).

[6] HashiCorp. *State*. [Estado, almacenamiento y precauciones](https://developer.hashicorp.com/terraform/language/state).

[7] Pulumi. *State & backends*. [Backends, checkpoints y refresh](https://www.pulumi.com/docs/iac/concepts/state-and-backends/).

[8] Bocaletto Luca. *Pong* [Código fuente, GPL-3.0]. [Commit 58927a56](https://github.com/bocaletto-luca/Pong/tree/58927a56aef0117aa290898d9b48d0f7ee0918b0).

[9] Ballara, J., Dutra, F. y Machado, M. (2026). *IaC en la práctica: caso de estudio en AWS*. Evidencia del proyecto: [mediciones intensivas](intensive-results.csv), [tabla histórica](HISTORICO_SIMPLE_MEDIO.md), [informe consolidado](RESULTADOS_REALES.md), `benchmark/bench.py` y logs locales.

[10] OpenTofu. *State and Plan Encryption*. [Cifrado nativo y precauciones](https://opentofu.org/docs/language/state/encryption/).
