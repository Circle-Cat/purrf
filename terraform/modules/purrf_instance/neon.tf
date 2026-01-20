resource "neon_project" "this" {
  name                      = local.neon_project_name
  pg_version                = 16
  region_id                 = "aws-us-east-1"
  org_id                    = var.neon_org_id
  history_retention_seconds = 21600
}

resource "neon_role" "this" {
  project_id = neon_project.this.id
  branch_id  = neon_project.this.default_branch_id
  name       = local.neon_role_name
}

resource "neon_database" "this" {
  project_id = neon_project.this.id
  branch_id  = neon_project.this.default_branch_id
  owner_name = neon_role.this.name
  name       = local.neon_db_name
}

