**Proyecto Final Cloud Computing**

**1. Integrantes del Equipo:**

* Nombre y Apellido 1: Joaquín Ballara
* Nombre y Apellido 2: Facundo Dutra
* Nombre y Apellido 3 (si aplica): Mauro Machado

**2. Área Temática y Título del Proyecto:**

* Categoría: 3.4 Automatización, GitOps e IaC
* Título del Trabajo: *IaC en la práctica: CloudFormation vs Terraform vs OpenTofu vs Pulumi sobre una arquitectura AWS de complejidad creciente*

**3. Pregunta u Objetivo Principal de Investigación:**

¿Cómo se comparan CloudFormation, Terraform, OpenTofu y Pulumi (Python) al aprovisionar una misma aplicación en AWS en tres niveles de complejidad (simple, media e intensiva), en términos de tiempo de despliegue y destrucción, verbosidad del código, calidad del *preview* de cambios, manejo de estado y rollback, y modularidad? Queremos determinar si la herramienta más conveniente cambia a medida que crece la complejidad de la infraestructura, y qué compromisos (*trade-offs*) implica cada elección. Dejamos fuera CDK de forma deliberada: al sintetizar a plantillas de CloudFormation, su comportamiento de despliegue queda cubierto por CloudFormation y lo que aporta es una capa de abstracción en lenguajes de programación, que ya evaluamos con Pulumi.

**4. Alcance de la Demostración Práctica (PoC o Caso de Estudio):**

* Tipo de entregable práctico: **PoC Técnica con Código/Demo**
* Descripción breve de lo que se va a mostrar/probar:
  Desplegaremos la misma aplicación web (un juego Pong de código abierto, servido como sitio estático) con las cuatro herramientas en AWS (región us-east-1), en tres niveles:
  * **Simple:** VPC + EC2 + S3.
  * **Medio:** VPC + ALB + ECS Fargate + RDS.
  * **Intensivo:** arquitectura de tres capas multi-AZ con Auto Scaling Group, ALB, RDS Multi-AZ, ElastiCache, S3 + CloudFront, roles IAM y alarmas de CloudWatch.

  Un script de benchmark automatizado (Python) ejecutará varias repeticiones de *preview → deploy → preview sin cambios → destroy* para cada herramienta y nivel, y generará una tabla comparativa con tiempos, líneas de código, cantidad de recursos y huella del estado. Complementaremos con escenarios de fallo y rollback, y con una demo en vivo del nivel simple (con video de respaldo de 2 minutos).

**5. Relación con los Contenidos del Curso:**

Infraestructura como Código (IaC), automatización de despliegues, servicios cloud (cómputo, almacenamiento, bases de datos, balanceo, CDN), redes en la nube (VPC, subredes, NAT, multi-AZ), contenedores (ECS Fargate) y principios cloud (elasticidad, alta disponibilidad, pago por uso).

**6. Herramientas / Tecnologías Principales a Utilizar:**

AWS CloudFormation, Terraform, OpenTofu, Pulumi (Python), AWS (us-east-1), AWS CLI, Python (script de benchmark), nginx, y la aplicación Pong de código abierto (GPL-3.0) fijada a un commit específico.
