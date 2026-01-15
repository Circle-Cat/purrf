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

**WARNING:**
**Do not forcibly terminate (Ctrl+C) Terraform while it is running.**