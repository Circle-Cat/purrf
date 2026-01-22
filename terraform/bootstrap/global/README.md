## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_cloudflare"></a> [cloudflare](#requirement\_cloudflare) | ~> 5.0 |
| <a name="requirement_google"></a> [google](#requirement\_google) | ~> 5.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_cloudflare"></a> [cloudflare](#provider\_cloudflare) | 5.15.0 |
| <a name="provider_google"></a> [google](#provider\_google) | 5.45.2 |
| <a name="provider_terraform"></a> [terraform](#provider\_terraform) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [cloudflare_dns_record.api_prod](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.api_test](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.cf_prod](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.cf_test](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.root_prod](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.root_test](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/dns_record) | resource |
| [cloudflare_pages_domain.purrf_io_prod](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/pages_domain) | resource |
| [cloudflare_pages_domain.purrf_io_test](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/pages_domain) | resource |
| [cloudflare_pages_project.purrf_production](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/pages_project) | resource |
| [cloudflare_ruleset.cors_headers](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/ruleset) | resource |
| [cloudflare_ruleset.global_waf](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/ruleset) | resource |
| [cloudflare_zero_trust_tunnel_cloudflared_config.gcp_tunnel_config](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/zero_trust_tunnel_cloudflared_config) | resource |
| [google_access_context_manager_access_policy.purrf_internal](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/access_context_manager_access_policy) | resource |
| [google_access_context_manager_service_perimeter.purrf_primary_perimeter](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/access_context_manager_service_perimeter) | resource |
| [google_project.circlecat_project_data](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/project) | data source |
| [google_project.main_gcp_project_data](https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/project) | data source |
| [terraform_remote_state.prod_env](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |
| [terraform_remote_state.test_env](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_circlecat_project_id"></a> [circlecat\_project\_id](#input\_circlecat\_project\_id) | n/a | `string` | `"circlecat"` | no |
| <a name="input_main_gcp_project_id"></a> [main\_gcp\_project\_id](#input\_main\_gcp\_project\_id) | n/a | `string` | `"purrf-452300"` | no |
| <a name="input_main_gcp_region"></a> [main\_gcp\_region](#input\_main\_gcp\_region) | GCP region | `string` | `"us-west1"` | no |
| <a name="input_organization_id"></a> [organization\_id](#input\_organization\_id) | n/a | `string` | `"352575165160"` | no |

## Outputs

No outputs.
