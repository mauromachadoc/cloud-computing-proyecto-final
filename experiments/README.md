# Etapa 4 — escenarios controlados

**No ejecutar sobre infraestructura de producción.** Cada experimento es independiente de los `tiers/` y utiliza nombres de recursos distintos. Los scripts solamente llaman a AWS si se pasa explícitamente `--execute`. Configurá presupuestos y verificá el perfil antes de operar. La arquitectura de los tres niveles es una *PoC*, no una aplicación empresarial; RDS/ElastiCache no son consumidos por Pong.

## A. Fallo de despliegue y rollback

Todos los ejemplos crean primero un bucket S3 y luego intentan asignarle una política que menciona **deliberadamente un ARN de recurso que no corresponde al bucket**. Esperamos un error en `PutBucketPolicy`. Si el proveedor validase la política antes de crear el bucket, también se documenta como un resultado diferente.

```bash
python benchmark/failure.py --tool cloudformation             # dry-run implícito
python benchmark/failure.py --tool cloudformation --profile cuenta-a --execute
python benchmark/failure.py --tool terraform --profile cuenta-a --execute
python benchmark/failure.py --tool opentofu --profile cuenta-a --execute
python benchmark/failure.py --tool pulumi --profile cuenta-a --execute
```

Cada ejecución guarda `results/failure-<tool>.json` y `results/logs/failure-<tool>.log`. **Comparar**: si hubo fallo esperado, qué recursos quedaron luego del error, comportamiento de rollback, errores de cleanup y pasos de recuperación. CloudFormation podría mantener temporalmente un stack `ROLLBACK_COMPLETE`, que el script intenta borrar. Terraform, OpenTofu y Pulumi pueden conservar el bucket parcialmente creado en su estado, y el script intenta `destroy`. Revisá la cuenta si el script anuncia `CLEANUP FAILED`.

No mezclar esta métrica con tiempo de un despliegue exitoso: son dos muestras de comportamiento distintas.

## B. Pérdida de estado local (preview sin apply)

**Primero aprovisioná manualmente** el nivel simple en la herramienta seleccionada. No uses `benchmark/bench.py` para ello, porque destruye la infraestructura al terminar.

```bash
cd tiers/01-simple/terraform
terraform init && terraform apply
cd ../../..
python benchmark/state_loss.py --tool terraform --tier simple --profile cuenta-a
python benchmark/state_loss.py --tool terraform --tier simple --profile cuenta-a --execute
# Revisar results/logs/state-loss-simple-terraform.log
cd tiers/01-simple/terraform
terraform plan
terraform destroy
```

Repetí con `tofu` cambiando `--tool opentofu` o con Pulumi (`pulumi login file://...`, `pulumi install`, `pulumi stack select dev --create`, `pulumi up`, script de estado, `pulumi destroy`). `state_loss.py` mueve el estado a `results/state-backups/`, ejecuta solamente un **preview**, y restaura el archivo o directorio en `finally`. Si el sistema operativo se interrumpe, la copia de seguridad puede requerir restauración manual. Nunca ejecutes `apply` con el estado oculto, ni borres la copia. **CloudFormation no mantiene un archivo de estado local**, por lo que no es equivalente perder un archivo local en ese caso.

Anotá: si se pueden planificar duplicados, si el stack se puede descubrir sin estado, si el preview da error y cómo se recupera. El ejemplo no simula pérdidas del estado administrado por AWS ni compara backends remotos.

## C. Modularidad / reutilización de un bucket privado

Los cuatro ejemplos definen el mismo recurso lógico reutilizable: bucket S3 con cifrado AES256 y bloqueo de acceso público.

- `modularity/terraform/modules/private_bucket` y `modularity/opentofu/modules/private_bucket`: módulo HCL local, invocado por `module "private_bucket"`.
- `modularity/pulumi/component.py`: `ComponentResource` de Python, invocado desde `__main__.py`.
- `modularity/cloudformation/child.yaml`: nested stack, invocado por `template.yaml`. CloudFormation necesita publicar la plantilla hija en S3 (paso adicional que debe contarse).

Terraform/OpenTofu y Pulumi siguen la secuencia `init/install → plan/preview → apply/up → destroy`. El ejemplo de CloudFormation requiere primero un bucket de plantillas controlado por tu cuenta y un `ChildTemplateUrl` público para el servicio CloudFormation (se recomienda URL S3 con acceso a través de las credenciales del mismo rol/usuario), por ejemplo:

```bash
# Sustituir ACCOUNT por el ID de la cuenta y ejecutar desde la raíz del repo.
aws s3 mb s3://iacbench-templates-ACCOUNT-us-east-1 --region us-east-1
aws s3 cp experiments/modularity/cloudformation/child.yaml s3://iacbench-templates-ACCOUNT-us-east-1/child.yaml
aws cloudformation deploy \
  --stack-name iacbench-modularity-cfn \
  --template-file experiments/modularity/cloudformation/template.yaml \
  --parameter-overrides ChildTemplateUrl=https://iacbench-templates-ACCOUNT-us-east-1.s3.us-east-1.amazonaws.com/child.yaml
aws cloudformation delete-stack --stack-name iacbench-modularity-cfn
aws cloudformation wait stack-delete-complete --stack-name iacbench-modularity-cfn
aws s3 rm s3://iacbench-templates-ACCOUNT-us-east-1/child.yaml
aws s3 rb s3://iacbench-templates-ACCOUNT-us-east-1
```

Comparar: archivos y LOC de definición versus invocación, forma de pasar parámetros/salidas, dependencia de publicar módulos, procedimientos de pruebas, reuso dentro de otras pilas y coste operacional. CloudFormation agrupa propiedades de S3 en un recurso; Terraform/OpenTofu/Pulumi dividen la configuración en varios recursos. No interpretar *cantidad de recursos* como número de servicios AWS. Los recursos no quedan destruidos automáticamente en estos ejemplos manuales; eliminarlos luego de compararlos.

## D. Diferencial nativo OpenTofu — cifrado de estado local

`state-encryption/opentofu` demuestra PBKDF2 + AES-GCM sobre `terraform_data` (no crea recursos AWS). No agregamos el cifrado a los benchmarks principales porque rompería la comparación HCL idéntico a Terraform y requiere gestionar claves.

```bash
cd experiments/state-encryption/opentofu
# Bash: export TF_VAR_passphrase='UNA_CONTRASENA_LARGA_Y_UNICA'
# PowerShell: $env:TF_VAR_passphrase='UNA_CONTRASENA_LARGA_Y_UNICA'
tofu init
tofu apply -auto-approve
tofu state list             # el estado sigue siendo utilizable por OpenTofu
# Inspeccionar manualmente terraform.tfstate: formato cifrado
# Conservar la contraseña hasta terminar la limpieza.
tofu destroy -auto-approve
```

No incluir la passphrase en capturas ni en el repo. En un caso real, usar un gestor de secretos o KMS. Referencia: https://opentofu.org/docs/language/state/encryption/

## Registro sugerido

| Caso | Tool | Preview/plan antes | Resultado fallo o estado oculto | Recursos remanentes | Cleanup | Recuperación | Observaciones |
|---|---|---|---|---|---|---|---|
| Fallo S3 | CFN/TF/Tofu/Pulumi | ... | ... | ... | ... | ... | ... |
| Pérdida state | CFN/TF/Tofu/Pulumi | ... | ... | ... | ... | ... | ... |
| Modularidad | CFN/TF/Tofu/Pulumi | ... | ... | ... | ... | ... | ... |
