variable "name" {
  description = "Name of the app registration, the resource group and the Azure Bot, e.g. purrf-bot-test."
  type        = string
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
