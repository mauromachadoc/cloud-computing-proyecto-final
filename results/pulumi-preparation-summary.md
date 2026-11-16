# Pulumi Preparation: Simple and Medium

Historical preparation report for October. The intensive extension is recorded below; the statements in this section describe only that earlier preparation.

Only `tiers/01-simple/pulumi` and `tiers/02-medium/pulumi` were prepared.
No AWS resources were created. No `up` or `destroy` was executed.
Intensive, Terraform, Tofu, CloudFormation, and `benchmark/bench.py` were not touched.
No credentials were inspected or modified by the helper, and no state contents were read or published.

## Results

| Tier | Install exit | Preview exit | Preview duration | Proposed creations |
| --- | --- | --- | --- | --- |
| simple | 0 | 0 | 10.954 s | 12: 11 AWS resources + Pulumi stack |
| medium | 0 | 0 | 10.859 s | 23: 22 AWS resources + Pulumi stack |

These are preview proposals, not deployed resources. Output values remain unknown.
All recorded commands exited 0; both `pip check` commands succeeded.
No failures or blockers were observed. Preview success does not verify deployment or runtime behavior.

## Local Configuration

- Stack: `dev` in each project, selected with `stack select dev --create`.
- Region: `aws:region=us-east-1`, `AWS_REGION=us-east-1`, `AWS_DEFAULT_REGION=us-east-1`.
- `PULUMI_CONFIG_PASSPHRASE` and `AWS_PAGER`: empty.
- `PULUMI_SKIP_UPDATE_CHECK=true`.
- Each command received its own `PULUMI_BACKEND_URL`, generated with `Path.as_uri()`.
- Simple backend: `file:///C:/Users/Macha/Documents/iac-comparison/tiers/01-simple/pulumi/.pulumi-state`.
- Medium backend: `file:///C:/Users/Macha/Documents/iac-comparison/tiers/02-medium/pulumi/.pulumi-state`.
- `pulumi install --non-interactive` created each project's local `venv`; no global Python packages were installed.
- SHA-256 comparisons confirmed `Pulumi.yaml`, `requirements.txt`, and `__main__.py` unchanged in both projects.
- CLI-generated local artifacts include `venv`, `.pulumi-state`, and stack configuration `Pulumi.dev.yaml`.

## Exact Versions

Both environments resolved the same packages. Pulumi CLI: `3.272.0`.
Python in both local virtual environments: `3.12.10`. AWS resource plugin: `6.83.4`.

```text
debugpy==1.8.22
dill==0.4.1
googleapis-common-protos==1.76.0
grpcio==1.84.1
opentelemetry-api==1.45.1
opentelemetry-exporter-otlp-common==0.66b1
opentelemetry-exporter-otlp-proto-common==1.45.1
opentelemetry-exporter-otlp-proto-grpc==1.45.1
opentelemetry-instrumentation==0.66b1
opentelemetry-instrumentation-grpc==0.66b1
opentelemetry-proto==1.45.1
opentelemetry-sdk==1.45.1
opentelemetry-semantic-conventions==0.66b1
packaging==26.3
parver==1.0.1.post0
pip==26.2.2
protobuf==6.33.6
pulumi==3.272.0
pulumi_aws==6.83.4
PyYAML==6.0.3
semver==3.1.0
setuptools==84.2.1
typing_extensions==4.16.0
wheel==0.48.0
wrapt==2.5.1
```

## Evidence

- `pulumi-simple-summary.json` and `pulumi-medium-summary.json`: commands, working directories, backend URIs, exit codes, durations, timeouts, and source-integrity result.
- `pulumi-simple-*.log` and `pulumi-medium-*.log`: per-command output, including preview, install, dependency freeze, plugin inventory, and dependency checks.
- `prepare_pulumi.py`: helper restricted to the two authorized tiers, with per-command timeouts and no deployment operations.

## Intensive extension — November 2026

The helper now also accepts `intensive`. Preparation completed without AWS resource creation: install, `pip check`, backend login, stack selection, region configuration, and preview all exited 0. Installation took 460.828 s; preview took 30.156 s and proposed 42 creations (including the Pulumi stack). The source integrity check passed.

The intensive environment resolved Pulumi SDK 3.276.0 and Pulumi AWS 6.83.4 with Python 3.12.10; CLI version and full dependency freeze are in `pulumi-intensive-cli-version.log` and `pulumi-intensive-dependencies.log`. These dependencies differ from the historical SDK 3.272.0 and are a limitation when comparing dates. The subsequent deployment measurements are documented in [INTENSIVO.md](INTENSIVO.md), separately from this preparation.

Evidence: `pulumi-intensive-summary.json` (local), `pulumi-intensive-*.log` (per-command output). Initial installation time is outside the benchmark; its measured setup reuses the prepared environment.
