terraform {
  required_version = ">= 1.6"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 5.0" } }
}
provider "aws" { region = "us-east-1" }
data "aws_caller_identity" "self" {}
data "aws_region" "current" {}
resource "aws_s3_bucket" "valid" {
  bucket = "iacbench-fail-tofu-${data.aws_caller_identity.self.account_id}-${data.aws_region.current.name}"
  force_destroy = true
}
resource "aws_s3_bucket_policy" "broken" {
  bucket = aws_s3_bucket.valid.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = "*", Action = "s3:GetObject",
      Resource = "arn:aws:s3:::iacbench-deliberately-wrong-resource/*" }]
  })
}
