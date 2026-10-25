# Benchmark results

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
