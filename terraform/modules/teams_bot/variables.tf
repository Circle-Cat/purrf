variable "name" {
  description = "Resource name of the resource group and the Azure Bot, and the prefix of the federated credentials, e.g. purrf-bot-test. Azure allows no spaces here."
  type        = string
}

variable "display_name" {
  description = "Name people see for the app registration and the Azure Bot, e.g. Purrf Notifications. Defaults to name. In Teams the name comes from the app manifest, not from here."
  type        = string
  default     = null
}

variable "location" {
  description = "Azure region of the resource group. The bot itself is always global."
  type        = string
  default     = "westus2"
}

variable "federated_identities" {
  description = "Workloads that may get tokens as the bot without a secret, as issuer and subject of their OIDC tokens."
  type = map(object({
    issuer  = string
    subject = string
  }))
  default = {}
}
