# Terraform Google Cloud Infrastructure Setup

./terraform contains Terraform code to create and manage Google Cloud resources including:

- Pub/Sub topics, subscriptions, and dead-letter queues
- Cloud Functions
- Cloud Scheduler jobs

## How to use

### Authenticate your Google Cloud account with Application Default Credentials:

```bash
gcloud auth application-default login
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


### Destroy the infrastructure

```bash
terraform destroy
```

**WARNING:**
**Do not forcibly terminate (Ctrl+C) Terraform while it is running.**