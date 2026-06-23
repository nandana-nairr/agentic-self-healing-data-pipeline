terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-south-1"
}

resource "aws_s3_bucket" "pipeline_data" {
  bucket = "pipeline-data-sh"

  tags = {
    Project     = "self-healing-pipeline"
    Environment = "dev"
  }
}

resource "aws_iam_user" "pipeline_user" {
  name = "artemis-dev"

  tags = {
    Project = "self-healing-pipeline"
  }
}

resource "aws_iam_user_policy_attachment" "s3_access" {
  user       = aws_iam_user.pipeline_user.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}