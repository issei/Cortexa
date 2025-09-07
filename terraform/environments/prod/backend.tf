terraform {
  backend "s3" {
    bucket = "cortexa-terraform-state-bucket-placeholder" # Replace with your actual S3 bucket name
    key    = "prod/terraform.tfstate"
    region = "us-east-1" # Replace with your desired AWS region
  }
}
