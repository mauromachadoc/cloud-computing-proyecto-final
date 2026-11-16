# Benchmark results

_Generated 2026-11-16T00:03:37 - times are medians of successful runs, in seconds._

| Tier | Tool | Runs ok/total | LOC | Resources | Preview (s) | Deploy (s) | No-op preview (s) | Destroy (s) | State | Est. cost/run (USD) |
|---|---|---|---|---|---|---|---|---|---|---|
| intensive | cloudformation | 1/2 | 342 | 40 | 37.6 | 954.8 | 4.8 | 496.6 | AWS-managed (no local file) (0 B) | 0.168 |
| intensive | terraform | 1/1 | 356 | 41 | 8.6 | 953.2 | 14.1 | 409.0 | local terraform.tfstate (86055 B) | 0.191 |
| intensive | opentofu | 1/1 | 356 | 41 | 9.0 | 952.4 | 13.8 | 452.3 | local terraform.tfstate (84074 B) | 0.197 |
| intensive | pulumi | 1/1 | 131 | 41 | 25.7 | 908.2 | 19.2 | 867.5 | local file backend (.pulumi-state/) (339802 B) | 0.249 |

## Histórico simple/medio

Las ocho corridas de octubre se conservan como informe histórico. Su CSV y logs originales no estaban presentes en este checkout; no se reconstruyeron ni mezclaron con las nuevas mediciones.

### Tabla histórica de octubre de 2026

_Generated 2026-10-25T04:12:43 - times are medians of successful runs, in seconds._

| Tier | Tool | Runs ok/total | LOC | Resources | Preview (s) | Deploy (s) | No-op preview (s) | Destroy (s) | State | Est. cost/run (USD) |
|---|---|---|---|---|---|---|---|---|---|---|
| simple | cloudformation | 1/1 | 105 | 10 | 33.5 | 63.9 | 2.1 | 64.2 | AWS-managed (no local file) (0 B) | 0.001 |
| simple | terraform | 1/1 | 127 | 11 | 5.5 | 44.9 | 8.6 | 50.8 | local terraform.tfstate (23185 B) | 0.001 |
| simple | opentofu | 1/1 | 127 | 11 | 6.3 | 46.2 | 12.4 | 50.5 | local terraform.tfstate (22457 B) | 0.001 |
| simple | pulumi | 1/1 | 108 | 11 | 14.6 | 55.5 | 14.1 | 43.7 | local file backend (.pulumi-state/) (84593 B) | 0.001 |
| medium | cloudformation | 1/1 | 199 | 23 | 36.6 | 373.1 | 3.8 | 528.7 | AWS-managed (no local file) (0 B) | 0.038 |
| medium | terraform | 1/1 | 205 | 22 | 8.9 | 353.6 | 12.9 | 468.3 | local terraform.tfstate (45666 B) | 0.035 |
| medium | opentofu | 1/1 | 205 | 22 | 8.5 | 364.3 | 14.1 | 465.3 | local terraform.tfstate (44711 B) | 0.035 |
| medium | pulumi | 1/1 | 79 | 22 | 13.3 | 360.7 | 21.8 | 586.4 | local file backend (.pulumi-state/) (193481 B) | 0.040 |
