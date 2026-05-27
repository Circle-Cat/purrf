# Read-only PostgreSQL access on prod.
#
# Pattern: a NOLOGIN group role (`readonly`) owns all grants and default
# privileges. Individual login users are members of the group and inherit
# its SELECT/USAGE/CONNECT. Adding a new user = one entry in
# `local.readonly_users` — no grant duplication.
#
# Passwords are TF-generated and exposed only via the sensitive
# `readonly_connection_uris` map output.
#
# Rotation:   `terraform taint random_password.readonly[\"<key>\"] && terraform apply`
# Revocation: remove the entry from `local.readonly_users` and apply.

locals {
  # key (short) → postgres role name. Key is what you pass to
  # `terraform output -json readonly_connection_uris | jq -r .<key>`.
  readonly_users = {
    daisy = "readonly_daisyisadaisy"
    ziqi  = "readonly_ziqi"
  }
}

resource "postgresql_role" "readonly_group" {
  name  = "readonly"
  login = false
}

resource "postgresql_grant" "readonly_db_connect" {
  database    = module.purrf_instance.neon_db_name
  role        = postgresql_role.readonly_group.name
  object_type = "database"
  privileges  = ["CONNECT"]
}

resource "postgresql_grant" "readonly_schema_usage" {
  database    = module.purrf_instance.neon_db_name
  role        = postgresql_role.readonly_group.name
  schema      = "public"
  object_type = "schema"
  privileges  = ["USAGE"]
}

resource "postgresql_grant" "readonly_table_select" {
  database    = module.purrf_instance.neon_db_name
  role        = postgresql_role.readonly_group.name
  schema      = "public"
  object_type = "table"
  objects     = []
  privileges  = ["SELECT"]
}

resource "postgresql_grant" "readonly_sequence_select" {
  database    = module.purrf_instance.neon_db_name
  role        = postgresql_role.readonly_group.name
  schema      = "public"
  object_type = "sequence"
  objects     = []
  privileges  = ["SELECT"]
}

# Future tables/sequences created by the owner role (e.g. via Alembic
# migrations) automatically get SELECT for the group — and therefore for
# every member. Without this, every new migration silently makes a table
# invisible to readonly users.
resource "postgresql_default_privileges" "readonly_future_tables" {
  database    = module.purrf_instance.neon_db_name
  role        = postgresql_role.readonly_group.name
  owner       = module.purrf_instance.neon_owner_role_name
  schema      = "public"
  object_type = "table"
  privileges  = ["SELECT"]
}

resource "postgresql_default_privileges" "readonly_future_sequences" {
  database    = module.purrf_instance.neon_db_name
  role        = postgresql_role.readonly_group.name
  owner       = module.purrf_instance.neon_owner_role_name
  schema      = "public"
  object_type = "sequence"
  privileges  = ["SELECT"]
}

resource "random_password" "readonly" {
  for_each = local.readonly_users
  length   = 40
  special  = false
}

resource "postgresql_role" "readonly" {
  for_each = local.readonly_users
  name     = each.value
  login    = true
  password = random_password.readonly[each.key].result
  roles    = [postgresql_role.readonly_group.name]

  # 60s — value is in milliseconds. Keeps a runaway analytical query
  # from pinning a Neon compute.
  statement_timeout = 60000
}
