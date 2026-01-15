# Create a Purrf instance for the test environment.
module "purrf_instance" {
  source = "../../modules/purrf_instance"

  env_name       = "test"
  gcp_project_id = "purrf-452300"
}
