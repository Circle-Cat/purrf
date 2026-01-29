## Requirements

No requirements.

## Providers

| Name | Version |
|------|---------|
| <a name="provider_archive"></a> [archive](#provider\_archive) | n/a |
| <a name="provider_auth0"></a> [auth0](#provider\_auth0) | n/a |
| <a name="provider_azuread"></a> [azuread](#provider\_azuread) | n/a |
| <a name="provider_google"></a> [google](#provider\_google) | n/a |
| <a name="provider_helm"></a> [helm](#provider\_helm) | n/a |
| <a name="provider_neon"></a> [neon](#provider\_neon) | n/a |
| <a name="provider_upstash"></a> [upstash](#provider\_upstash) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [auth0_client.purrf_auth0](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/client) | resource |
| [auth0_connection.db](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/connection) | resource |
| [auth0_connection.email](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/connection) | resource |
| [auth0_connection_clients.disable_db_for_all](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/connection_clients) | resource |
| [auth0_connection_clients.email_assoc](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/connection_clients) | resource |
| [auth0_custom_domain.purrf_custom_domain](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/custom_domain) | resource |
| [auth0_prompt.prompts](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/prompt) | resource |
| [auth0_prompt_custom_text.en_login_id](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/prompt_custom_text) | resource |
| [auth0_trigger_actions.post_login](https://registry.terraform.io/providers/auth0/auth0/latest/docs/resources/trigger_actions) | resource |
| [azuread_application_federated_identity_credential.azure_wif](https://registry.terraform.io/providers/hashicorp/azuread/latest/docs/resources/application_federated_identity_credential) | resource |
| [google_cloudfunctions_function.functions](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloudfunctions_function) | resource |
| [google_cloudfunctions_function_iam_member.invoker](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloudfunctions_function_iam_member) | resource |
| [google_project_iam_member.cloud_build_artifactregistry_creator](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.cloud_build_storage_viewer](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.function_pubsub](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.function_subscriber](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.pubsub_auto_pub_to_dlq](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_iam_member.pubsub_auto_sub](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member) | resource |
| [google_project_service.access_context_manager](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_service) | resource |
| [google_project_service.cloud_functions](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_service) | resource |
| [google_pubsub_subscription.dlq_subscriptions](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_subscription) | resource |
| [google_pubsub_subscription.subscriptions](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_subscription) | resource |
| [google_pubsub_topic.dlq](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_topic) | resource |
| [google_pubsub_topic.topics](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_topic) | resource |
| [google_service_account.function_sa](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_account) | resource |
| [google_service_account_iam_member.purrf_service_wi](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_account_iam_member) | resource |
| [google_storage_bucket.function_bucket](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket) | resource |
| [google_storage_bucket_iam_binding.purrf_internal](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket_iam_binding) | resource |
| [google_storage_bucket_object.function_zips](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket_object) | resource |
| [helm_release.purrf_app](https://registry.terraform.io/providers/hashicorp/helm/latest/docs/resources/release) | resource |
| [neon_database.this](https://registry.terraform.io/providers/kislerdm/neon/latest/docs/resources/database) | resource |
| [neon_project.this](https://registry.terraform.io/providers/kislerdm/neon/latest/docs/resources/project) | resource |
| [neon_role.this](https://registry.terraform.io/providers/kislerdm/neon/latest/docs/resources/role) | resource |
| [upstash_redis_database.redis](https://registry.terraform.io/providers/upstash/upstash/latest/docs/resources/redis_database) | resource |
| [archive_file.function_zips](https://registry.terraform.io/providers/hashicorp/archive/latest/docs/data-sources/file) | data source |
| [google_compute_default_service_account.default](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_default_service_account) | data source |
| [google_project.main_gcp_project_data](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/project) | data source |
| [neon_branch_endpoints.all](https://registry.terraform.io/providers/kislerdm/neon/latest/docs/data-sources/branch_endpoints) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_auth0_callbacks"></a> [auth0\_callbacks](#input\_auth0\_callbacks) | Allowed callback URLs for Auth0 | `list(string)` | n/a | yes |
| <a name="input_auth0_logout_urls"></a> [auth0\_logout\_urls](#input\_auth0\_logout\_urls) | Allowed logout URLs for Auth0 | `list(string)` | n/a | yes |
| <a name="input_base_domain"></a> [base\_domain](#input\_base\_domain) | Base domain name | `string` | `"purrf.io"` | no |
| <a name="input_cloudflare_account_id"></a> [cloudflare\_account\_id](#input\_cloudflare\_account\_id) | Cloudflare Account ID | `string` | n/a | yes |
| <a name="input_cloudflare_tunnel_id"></a> [cloudflare\_tunnel\_id](#input\_cloudflare\_tunnel\_id) | Cloudflare Tunnel ID | `string` | n/a | yes |
| <a name="input_cloudflare_zone_id"></a> [cloudflare\_zone\_id](#input\_cloudflare\_zone\_id) | Cloudflare Zone ID | `string` | n/a | yes |
| <a name="input_env_name"></a> [env\_name](#input\_env\_name) | Environment name: prod, test, or staging | `string` | n/a | yes |
| <a name="input_gcp_project_id"></a> [gcp\_project\_id](#input\_gcp\_project\_id) | GCP project ID | `string` | n/a | yes |
| <a name="input_gcp_region"></a> [gcp\_region](#input\_gcp\_region) | GCP region | `string` | `"us-west1"` | no |
| <a name="input_gerrit_http_pass"></a> [gerrit\_http\_pass](#input\_gerrit\_http\_pass) | n/a | `string` | n/a | yes |
| <a name="input_gerrit_producer_code_dir"></a> [gerrit\_producer\_code\_dir](#input\_gerrit\_producer\_code\_dir) | The relative path to the Gerrit producer source code directory. | `string` | n/a | yes |
| <a name="input_gerrit_producer_entry_point"></a> [gerrit\_producer\_entry\_point](#input\_gerrit\_producer\_entry\_point) | The name of the Python function to be executed for Gerrit events. | `string` | n/a | yes |
| <a name="input_image_tag"></a> [image\_tag](#input\_image\_tag) | Deployed image tag | `string` | n/a | yes |
| <a name="input_jira_password"></a> [jira\_password](#input\_jira\_password) | n/a | `string` | n/a | yes |
| <a name="input_microsoft_chat_code_dir"></a> [microsoft\_chat\_code\_dir](#input\_microsoft\_chat\_code\_dir) | The relative path to the Microsoft Chat producer source code directory. | `string` | n/a | yes |
| <a name="input_microsoft_chat_entry_point"></a> [microsoft\_chat\_entry\_point](#input\_microsoft\_chat\_entry\_point) | The name of the Python function to be executed for Microsoft Chat. | `string` | n/a | yes |
| <a name="input_microsoft_lifecycle_code_dir"></a> [microsoft\_lifecycle\_code\_dir](#input\_microsoft\_lifecycle\_code\_dir) | The relative path to the Microsoft Lifecycle handler source code directory. | `string` | n/a | yes |
| <a name="input_microsoft_lifecycle_entry_point"></a> [microsoft\_lifecycle\_entry\_point](#input\_microsoft\_lifecycle\_entry\_point) | The name of the Python function to be executed for Microsoft Lifecycle events. | `string` | n/a | yes |
| <a name="input_neon_org_id"></a> [neon\_org\_id](#input\_neon\_org\_id) | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_auth0_client_id"></a> [auth0\_client\_id](#output\_auth0\_client\_id) | n/a |
| <a name="output_computed_domains"></a> [computed\_domains](#output\_computed\_domains) | Computed domain names for this Purrf instance. |
| <a name="output_default_account"></a> [default\_account](#output\_default\_account) | n/a |
| <a name="output_neon_database_owner"></a> [neon\_database\_owner](#output\_neon\_database\_owner) | n/a |
| <a name="output_neon_default_branch_id"></a> [neon\_default\_branch\_id](#output\_neon\_default\_branch\_id) | n/a |
| <a name="output_neon_project_id"></a> [neon\_project\_id](#output\_neon\_project\_id) | n/a |
| <a name="output_redis_endpoint"></a> [redis\_endpoint](#output\_redis\_endpoint) | n/a |
| <a name="output_redis_password"></a> [redis\_password](#output\_redis\_password) | n/a |
| <a name="output_redis_port"></a> [redis\_port](#output\_redis\_port) | n/a |
| <a name="output_resource_prefix"></a> [resource\_prefix](#output\_resource\_prefix) | Resource name prefix used by this module. |
