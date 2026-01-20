## Requirements

No requirements.

## Providers

| Name | Version |
|------|---------|
| <a name="provider_auth0"></a> [auth0](#provider\_auth0) | n/a |
| <a name="provider_google"></a> [google](#provider\_google) | n/a |
| <a name="provider_neon"></a> [neon](#provider\_neon) | n/a |
| <a name="provider_upstash"></a> [upstash](#provider\_upstash) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [auth0_client.purrf_auth0](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/client) | resource |
| [google_project_iam_member.pubsub_auto_pub_to_dlq](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.pubsub_auto_sub](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_pubsub_subscription.dlq_subscriptions](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_subscription) | resource |
| [google_pubsub_subscription.subscriptions](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_subscription) | resource |
| [google_pubsub_topic.dlq](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_topic) | resource |
| [google_pubsub_topic.topics](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_topic) | resource |
| [neon_database.this](https://registry.terraform.io/providers/kislerdm/neon/latest/docs/resources/database) | resource |
| [neon_project.this](https://registry.terraform.io/providers/kislerdm/neon/latest/docs/resources/project) | resource |
| [neon_role.this](https://registry.terraform.io/providers/kislerdm/neon/latest/docs/resources/role) | resource |
| [upstash_redis_database.redis](https://registry.terraform.io/providers/upstash/upstash/latest/docs/resources/redis_database) | resource |
| [google_project.main_gcp_project_data](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/project) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_base_domain"></a> [base\_domain](#input\_base\_domain) | Base domain name | `string` | `"purrf.io"` | no |
| <a name="input_env_name"></a> [env\_name](#input\_env\_name) | Environment name: prod, test, or staging | `string` | n/a | yes |
| <a name="input_gcp_project_id"></a> [gcp\_project\_id](#input\_gcp\_project\_id) | GCP project ID | `string` | n/a | yes |
| <a name="input_gcp_region"></a> [gcp\_region](#input\_gcp\_region) | GCP region | `string` | `"us-west1"` | no |
| <a name="input_neon_org_id"></a> [neon\_org\_id](#input\_neon\_org\_id) | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_auth0_client_id"></a> [auth0\_client\_id](#output\_auth0\_client\_id) | n/a |
| <a name="output_computed_domains"></a> [computed\_domains](#output\_computed\_domains) | Computed domain names for this Purrf instance. |
| <a name="output_neon_database_user"></a> [neon\_database\_user](#output\_neon\_database\_user) | n/a |
| <a name="output_neon_default_branch_id"></a> [neon\_default\_branch\_id](#output\_neon\_default\_branch\_id) | n/a |
| <a name="output_neon_project_id"></a> [neon\_project\_id](#output\_neon\_project\_id) | n/a |
| <a name="output_redis_endpoint"></a> [redis\_endpoint](#output\_redis\_endpoint) | n/a |
| <a name="output_resource_prefix"></a> [resource\_prefix](#output\_resource\_prefix) | Resource name prefix used by this module. |
