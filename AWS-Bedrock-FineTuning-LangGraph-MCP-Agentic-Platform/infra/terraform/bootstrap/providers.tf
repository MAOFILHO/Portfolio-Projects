provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project    = "bedrock-platform"
      ManagedBy  = "terraform"
      CostCenter = "bedrock-platform-bootstrap"
    }
  }
}
