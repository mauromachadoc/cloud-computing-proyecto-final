# Resumen Ejecutivo

## IaC en AWS: CloudFormation, Terraform, OpenTofu y Pulumi

**Proyecto Final de Cloud Computing · Universidad Católica del Uruguay**  
**Equipo:** Joaquín Ballara, Facundo Dutra y Mauro Machado. **Fecha:** 25/10/2026.

### Objetivo Y Hallazgo Principal

Se compararon cuatro herramientas de infraestructura como código (IaC) al desplegar la misma aplicación Pong en AWS `us-east-1`, con dos niveles de complejidad. Se realizaron ocho ciclos reales: una ejecución por herramienta y nivel. **Los ocho desplegaron correctamente, sirvieron Pong por HTTP y completaron su destrucción.** En el nivel medio, el deploy varió entre 353,62 y 373,05 segundos. El hallazgo central del caso es que las esperas de aprovisionamiento y estabilización de AWS resultaron más determinantes que las diferencias observadas entre motores. No se identifica un ganador universal [9].

### Marco Teórico Y Comparativa

IaC expresa la infraestructura en archivos reproducibles y versionables. El modelo declarativo describe el estado deseado; un motor resuelve dependencias y solicita cambios mediante las API del proveedor. El plan o preview permite inspeccionar operaciones antes de ejecutarlas. El estado relaciona las declaraciones con los recursos existentes; su custodia es una responsabilidad operativa, no solo un detalle de almacenamiento [1–4, 6–7].

| Herramienta | Modelo utilizado | Diferencial y responsabilidad |
|---|---|---|
| CloudFormation | Plantillas YAML, stacks y change sets | Integración nativa AWS y estado administrado por el servicio [1]. |
| Terraform | HCL declarativo, plan y apply | Proveedores para múltiples plataformas; requiere gestionar backend y estado [2, 6]. |
| OpenTofu | HCL declarativo, plan y apply | Cifrado nativo de estado y planes como capacidad diferencial; no se activó en esta prueba [3, 10]. |
| Pulumi | Python que declara recursos y dependencias | Permite abstracciones del lenguaje; agrega SDK, entorno Python y elección de backend [4, 7]. |

Usar Python no convierte el despliegue en una secuencia manual de scripts: el motor Pulumi conserva la resolución de dependencias y el estado deseado. Asimismo, un preview sin cambios es una señal de estabilidad de la configuración, pero no equivale a una auditoría uniforme de drift entre herramientas.

### Arquitectura Del Caso

**Simple:** VPC, una subred pública, Internet Gateway, rutas, grupo de seguridad y EC2 `t3.micro` con Amazon Linux 2023 y nginx. Un bucket S3 privado, versionado y cifrado es independiente del sitio. Pong se descarga al arrancar desde un commit fijo GPL-3.0 [8–9].

**Medio:** VPC en dos zonas de disponibilidad, dos subredes públicas para ALB y ECS Fargate, y dos privadas para datos. Una tarea de 0,25 vCPU/0,5 GiB recibe tráfico del ALB y utiliza IP pública para salir a Internet, sin NAT Gateway. PostgreSQL 16.15 corre en RDS `db.t3.micro` single-AZ. Fargate evita administrar servidores del contenedor [5].

`Internet → EC2/nginx/Pong` en simple; `Internet → ALB → ECS/Pong` en medio. **RDS no es utilizado por Pong**: incrementa la complejidad de IaC, no su funcionalidad. Dos zonas para las subredes no implican alta disponibilidad completa: hay una tarea y RDS single-AZ. El nivel intensivo quedó fuera de la ejecución autorizada [9].

<!-- pagebreak -->

### Método Y Resultados

El orquestador ejecutó secuencialmente `init → preview → deploy → preview sin cambios → verificación HTTP → destroy`. Midió tiempo de pared, líneas efectivas de código (LOC), recursos y huella del estado. HTTP exigió código 200 y el título de Pong antes de destruir; se cronometró por separado. Los proveedores y dependencias se instalaron previamente: init es una medición **warm**, no una instalación desde cero [9].

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

**Interpretación temporal.** Terraform tuvo el menor deploy en ambos niveles; Pulumi eliminó antes el simple y OpenTofu el medio. No hay una única herramienta que lidere todas las operaciones. En medio, la diferencia de deploy entre extremos fue 19,43 s, apenas 5,49 % respecto del menor valor. El salto simple–medio multiplicó el deploy entre 5,84 y 7,88 veces, y destroy entre 8,24 y 13,43 veces: el costo temporal creció más que el inventario, porque cambió la naturaleza de los servicios [9].

Los logs de Terraform, OpenTofu y Pulumi registran 321–332 s para crear RDS y 134–144 s para ALB. Son ramas parcialmente paralelas, no tiempos sumables. RDS fue una espera determinante de creación; ECS tardó 427–435 s en eliminarse. En Pulumi, el borrado de ALB y RDS comenzó después de finalizar ECS, lo que contribuyó a su mayor destroy medio. Esto explica parte del patrón sin atribuir toda la diferencia al motor; también influyen dependencias, proveedores y sondeo [9].

**Código y estado.** Pulumi fue más compacto en medio: 79 LOC frente a 205 en HCL, un 61,46 % menos. Su reducción desde 108 LOC del simple refleja el estilo y la compactación del código, no una modularidad demostrada. Los conteos de recursos tampoco son homogéneos: opciones integradas en un recurso pueden representarse por separado en otro proveedor.

El estado medio midió 45.666 B en Terraform, 44.711 B en OpenTofu y 193.481 B en Pulumi. Se comparó un archivo HCL con todo un directorio de backend Pulumi; **no son medidas equivalentes de eficiencia**. CloudFormation registró 0 B locales porque AWS administra su estado. No se probaron pérdida de estado, colaboración ni recuperación [6–7, 9].

<!-- pagebreak -->

### Conclusión Y Recomendación

Las cuatro herramientas resultaron viables para las dos arquitecturas. **Terraform/OpenTofu** son candidatos sólidos si el equipo prioriza HCL y planes explícitos: sus tiempos fueron cercanos y no justifican elegir uno únicamente por rendimiento. **Pulumi** es atractivo para un equipo afín a Python y produjo menos texto, aunque exige gestionar sus dependencias y considerar el destroy observado en pipelines efímeros. **CloudFormation** resulta coherente con una estrategia centrada en AWS y estado administrado, aceptando el procedimiento de change sets. Estas recomendaciones combinan resultados observados y capacidades documentadas, no ventajas operativas exhaustivamente probadas [1–4, 9].

La decisión debe priorizar conocimiento del equipo, claridad del código, operación del estado y limpieza, además del cronómetro. En este caso, **el nivel medio tardó más en destruirse que en crearse con las cuatro herramientas**. Por ello, un pipeline debe reservar tiempo para liberar servicios y comprobar remanentes antes de iniciar otra corrida.

### Alcance, Seguridad Y Costos

Se dispone de una observación por combinación: es suficiente para interpretar este caso, pero no para estimar variabilidad ni generalizar un ranking. Los no-op no tuvieron igual cobertura de drift; los proveedores fueron AWS 5.100.0 en HCL y 6.83.4 en Pulumi. La imagen `nginx:stable-alpine` es mutable y la descarga de Pong/CDN introduce dependencias externas. HTTP no prueba una sesión interactiva ni disponibilidad sostenida. No se ejecutaron el nivel intensivo ni los experimentos de rollback, pérdida de estado y modularidad [9].

La auditoría final devolvió inventarios vacíos dentro de su alcance. Los créditos reportados pasaron de 118,80 a 138,80 USD, consistentes con una recompensa RDS de 20 USD; no determinan el costo real por el posible retraso de facturación. Los 0,1506 USD del benchmark son una heurística, no una factura. Antes de ampliar el estudio corresponde revisar cargos, configurar presupuesto, fijar imágenes y repetir mediciones; el nivel intensivo requiere autorización separada [9].

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

[9] Ballara, J., Dutra, F. y Machado, M. (2026). *IaC en la práctica: caso de estudio en AWS*. Evidencia primaria del proyecto: [mediciones CSV](results.csv), [informe consolidado](RESULTADOS_REALES.md), `benchmark/bench.py` y `results/logs/`.

[10] OpenTofu. *State and Plan Encryption*. [Cifrado nativo y precauciones](https://opentofu.org/docs/language/state/encryption/).
