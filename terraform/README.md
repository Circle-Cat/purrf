# Terraform Infrastructure Setup

This directory manages the Terraform infrastructure for Purrf, organized by environment and reusable modules.

## Directory Structure
```text
terraform/
├── environments/
│   ├── golbal/   # Shared global infrastructure
│   ├── prod/
│   ├── staging/
│   └── test/
├── modules
│   └── purrf_instance
└── README.md
```

## Prerequisites

### Authenticate your Google Cloud account with Application Default Credentials:

```bash
gcloud auth application-default login
```
### Authenticate your Azure account with Application Default Credentials:
```bash
az login --use-device-code
```
## How to use

*Always run Terraform commands inside a specific environment directory
(e.g. environments/test, environments/staging, or environments/prod)*

### Select an environment

```bash
cd terraform/environments/test
```

### Initialize Terraform

```bash
terraform init
```

### Preview the planned infrastructure

```bash
terraform plan
```

### Apply the configuration

```bash
terraform apply
```
Confirm by typing yes when prompted.


### Destroy the infrastructure(if needed)

```bash
terraform destroy
```

### Use terraform-docs to generate README.md

Install terraform-docs:
```bash
go install github.com/terraform-docs/terraform-docs@v0.21.0

Generate the README:
```bash
terraform-docs markdown table . > README.md
```


**WARNING:**
**Do not forcibly terminate (Ctrl+C) Terraform while it is running.**