resource "auth0_client" "purrf_auth0" {
  description          = "Managed by Terraform"
  name                 = "Purrf (${var.env_name})"
  allowed_clients      = []
  allowed_logout_urls  = var.auth0_logout_urls
  allowed_origins      = []
  app_type             = "regular_web"
  callbacks            = var.auth0_callbacks
  client_aliases       = []
  client_metadata      = {}
  compliance_level     = null
  cross_origin_auth    = false
  cross_origin_loc     = null
  custom_login_page    = null
  custom_login_page_on = true
  encryption_key       = null
  form_template        = null
  grant_types = [
    "authorization_code",
    "implicit",
    "refresh_token",
    "client_credentials",
    # Required by /api/auth/emails/verify (and /emails/delete) — backend trades
    # a passwordless OTP for an id_token via Auth0's passwordless OTP grant
    # type.
    "http://auth0.com/oauth/grant-type/passwordless/otp",
  ]
  initiate_login_uri                                   = null
  is_first_party                                       = true
  is_token_endpoint_ip_header_trusted                  = false
  logo_uri                                             = "https://circlecat.org/wp-content/uploads/2022/12/cropped-circlecat-3.png"
  oidc_conformant                                      = true
  organization_require_behavior                        = null
  organization_usage                                   = null
  require_proof_of_possession                          = false
  require_pushed_authorization_requests                = false
  resource_server_identifier                           = null
  skip_non_verifiable_callback_uri_confirmation_prompt = "null"
  sso                                                  = false
  sso_disabled                                         = false
  web_origins                                          = []
  default_organization {
    disable         = true
    flows           = []
    organization_id = null
  }
  jwt_configuration {
    alg                 = "RS256"
    lifetime_in_seconds = 36000
    scopes              = {}
    secret_encoded      = false
  }
  native_social_login {
    apple {
      enabled = false
    }
    facebook {
      enabled = false
    }
    google {
      enabled = false
    }
  }
  refresh_token {
    expiration_type              = "non-expiring"
    idle_token_lifetime          = 2592000
    infinite_idle_token_lifetime = true
    infinite_token_lifetime      = true
    leeway                       = 0
    rotation_type                = "non-rotating"
    token_lifetime               = 31557600
  }
}

resource "auth0_client_credentials" "purrf_auth0" {
  client_id             = auth0_client.purrf_auth0.client_id
  authentication_method = "client_secret_post"
}

resource "auth0_custom_domain" "purrf_custom_domain" {
  domain     = local.domains.login
  type       = "auth0_managed_certs"
  tls_policy = "recommended"
}

# Auth0 only registers the custom hostname with its Cloudflare-for-SaaS edge
# after verification succeeds. Without this, the CNAME exists in DNS but
# requests to the login domain hit Cloudflare with no tenant mapping and
# fail with Error 1000.
resource "auth0_custom_domain_verification" "purrf_custom_domain" {
  custom_domain_id = auth0_custom_domain.purrf_custom_domain.id

  timeouts {
    create = "15m"
  }
}


resource "auth0_connection" "db" {
  name     = "Username-Password-Authentication"
  strategy = "auth0"

  options {
    disable_signup         = true
    brute_force_protection = true
  }
}

resource "auth0_connection_clients" "disable_db_for_all" {
  connection_id   = auth0_connection.db.id
  enabled_clients = [] # Keep this empty to ensure Terraform removes all associated applications.
}

resource "auth0_connection" "email" {
  name                 = "email"
  is_domain_connection = false
  strategy             = "email"
  authentication {
    active = true
  }
  connected_accounts {
    active = false
  }
  options {
    api_enable_users       = false
    brute_force_protection = true
    disable_signup         = false
    from                   = "{{ application.name }} <root@auth0.com>"
    subject                = "Welcome to {{ application.name }}"
    name                   = "email"
    syntax                 = "liquid"
    totp {
      length    = 6
      time_step = 180
    }
  }
}

resource "auth0_connection_clients" "email_assoc" {
  connection_id   = auth0_connection.email.id
  enabled_clients = [auth0_client.purrf_auth0.id]
}

resource "auth0_prompt" "prompts" {
  identifier_first               = true
  universal_login_experience     = "new"
  webauthn_platform_first_factor = false
}

resource "auth0_prompt_custom_text" "en_login_id" {
  prompt   = "login-id"
  language = "en"
  body = jsonencode({
    "login-id" : {
      "description" : "Log in to Purrf to continue your application.",
    }
  })
}

# Google social connection backed by our own Google OAuth client (not the
# Auth0 dev-keys shared client). Domain allowlist is enforced by a post-login
# Action attached manually on the Auth0 dashboard — Actions API isn't exposed
# on the Free plan.
resource "auth0_connection" "google" {
  name         = "google-oauth2"
  display_name = "Google"
  strategy     = "google-oauth2"
  options {
    client_id     = var.auth0_google_client_id
    client_secret = var.auth0_google_client_secret
  }
}

resource "auth0_connection_clients" "google" {
  connection_id   = auth0_connection.google.id
  enabled_clients = [auth0_client.purrf_auth0.id]
}

# Used to construct the Management API audience URL (always the default
# *.auth0.com tenant domain, not the Cloudflare-fronted custom domain).
data "auth0_tenant" "current" {}

# M2M client used by the "Link Accounts with Same Verified Email" post-login
# Action to call the Management API (find users by email, link identities).
# Action code lives in the Auth0 Dashboard; only credentials are managed here.
resource "auth0_client" "link_action_m2m" {
  name        = "Link Action M2M (${var.env_name})"
  description = "Managed by Terraform. Backs the post-login account-linking Action."
  app_type    = "non_interactive"
  grant_types = ["client_credentials"]
}

resource "auth0_client_credentials" "link_action_m2m" {
  client_id             = auth0_client.link_action_m2m.id
  authentication_method = "client_secret_post"
}

resource "auth0_client_grant" "link_action_m2m" {
  client_id = auth0_client.link_action_m2m.id
  audience  = "https://${data.auth0_tenant.current.domain}/api/v2/"
  scopes    = ["read:users", "update:users"]
}

