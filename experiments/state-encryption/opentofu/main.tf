# OpenTofu-only: encrypted local state, zero AWS resources / zero AWS cost.
# Provide a long unique secret through TF_VAR_passphrase (do not commit it).
variable "passphrase" {
  type      = string
  sensitive = true
  validation {
    condition     = length(var.passphrase) >= 16
    error_message = "Use a passphrase of at least 16 characters."
  }
}
terraform {
  required_version = ">= 1.6"
  encryption {
    key_provider "pbkdf2" "local" {
      passphrase = var.passphrase
    }
    method "aes_gcm" "local" {
      keys = key_provider.pbkdf2.local
    }
    state {
      method = method.aes_gcm.local
      enforced = true
    }
    plan {
      method = method.aes_gcm.local
      enforced = true
    }
  }
}
resource "terraform_data" "sample" {
  input = "local-encryption-test"
}
output "example" { value = terraform_data.sample.output }
