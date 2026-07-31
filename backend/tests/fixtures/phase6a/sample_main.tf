variable "region" {
  type    = string
  default = "eu-west-1"
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

module "network" {
  source = "./modules/network"
  region = var.region
}

resource "aws_s3_bucket" "logs" {
  bucket = "app-logs-${data.aws_caller_identity.current.account_id}"

  depends_on = [
    module.network,
  ]
}

resource "aws_iam_role" "ci" {
  name = "ci-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

output "bucket_name" {
  value = aws_s3_bucket.logs.bucket
}
