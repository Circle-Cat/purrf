resource "auth0_client" "purrf_auth0" {
  description                                          = "Managed by Terraform"
  name                                                 = "Purrf (${var.env_name})"
  allowed_clients                                      = []
  allowed_logout_urls                                  = var.auth0_logout_urls
  allowed_origins                                      = []
  app_type                                             = "regular_web"
  callbacks                                            = var.auth0_callbacks
  client_aliases                                       = []
  client_metadata                                      = {}
  compliance_level                                     = null
  cross_origin_auth                                    = false
  cross_origin_loc                                     = null
  custom_login_page                                    = null
  custom_login_page_on                                 = true
  encryption_key                                       = null
  form_template                                        = null
  grant_types                                          = ["authorization_code", "implicit", "refresh_token", "client_credentials"]
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

resource "auth0_custom_domain" "purrf_custom_domain" {
  domain     = local.domains.login
  type       = "auth0_managed_certs"
  tls_policy = "recommended"
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
    disable_signup         = true
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
      "description" : "Log in as an external mentee using your email address used in the application.",
      "federatedConnectionButtonText" : "Log in as a Googler mentor"
    }
  })
}

resource "auth0_trigger_actions" "post_login" {
  trigger = "post-login"
  actions {
    display_name = "googlers"
    id           = "3f25be15-8881-416d-80c8-f7eabaef662c"
  }
}

# Auth0 Free plan includes a built-in `google-oauth2` social connection.
# We use this default connection, but to restrict allowed user domains,
# we manually add a post-login Action and attach it to the Login trigger
# (start -> action -> completed). This must be done manually on the Free plan.
