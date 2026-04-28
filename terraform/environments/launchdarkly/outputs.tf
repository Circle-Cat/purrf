output "project_key" {
  value = launchdarkly_project.purrf.key
}

output "client_side_ids" {
  value = {
    for env in launchdarkly_project.purrf.environments :
    env.key => env.client_side_id
  }
  sensitive = true
}

output "mobile_keys" {
  value = {
    for env in launchdarkly_project.purrf.environments :
    env.key => env.mobile_key
  }
  sensitive = true
}

output "api_keys" {
  value = {
    for env in launchdarkly_project.purrf.environments :
    env.key => env.api_key
  }
  sensitive = true
}
