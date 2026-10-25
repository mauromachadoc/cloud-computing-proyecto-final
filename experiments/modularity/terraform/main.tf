terraform {
  required_version = ">= 1.6"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 5.0" } }
}
provider "aws" { region = "us-east-1" }
data "aws_caller_identity" "self" {}
data "aws_region" "current" {}
module "private_bucket" {
  source = "./modules/private_bucket"
  name = "iacbench-module-tf-${data.aws_caller_identity.self.account_id}-${data.aws_region.current.name}"
}
output "bucket_name" { value = module.private_bucket.name }
