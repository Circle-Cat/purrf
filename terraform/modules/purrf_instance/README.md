## Requirements

No requirements.

## Providers

| Name | Version |
|------|---------|
| <a name="provider_upstash"></a> [upstash](#provider\_upstash) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [upstash_redis_database.redis](https://registry.terraform.io/providers/upstash/upstash/latest/docs/resources/redis_database) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_base_domain"></a> [base\_domain](#input\_base\_domain) | Base domain name | `string` | `"purrf.io"` | no |
| <a name="input_env_name"></a> [env\_name](#input\_env\_name) | Environment name: prod, test, or staging | `string` | n/a | yes |
| <a name="input_gcp_project_id"></a> [gcp\_project\_id](#input\_gcp\_project\_id) | GCP project ID | `string` | n/a | yes |
| <a name="input_gcp_region"></a> [gcp\_region](#input\_gcp\_region) | GCP region | `string` | `"us-west1"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_computed_domains"></a> [computed\_domains](#output\_computed\_domains) | Computed domain names for this Purrf instance. |
| <a name="output_redis_endpoint"></a> [redis\_endpoint](#output\_redis\_endpoint) | n/a |
| <a name="output_resource_prefix"></a> [resource\_prefix](#output\_resource\_prefix) | Resource name prefix used by this module. |
