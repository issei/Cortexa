terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "lambda_exec_role" {
  name = "cortexa-lambda-exec-role-prod"

  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Action    = "sts:AssumeRole",
        Effect    = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  ]
}

resource "aws_sns_topic" "alerts" {
  name = "cortexa-alerts-topic-prod"
}

module "lambda" {
  for_each = var.functions

  source = "../../modules/lambda"

  function_name         = "${each.key}-prod"
  handler               = var.lambda_handler
  runtime               = var.lambda_runtime
  source_path           = each.value.source_path
  role_arn              = aws_iam_role.lambda_exec_role.arn
  memory_size           = each.value.memory_size
  timeout               = each.value.timeout
  environment_variables = each.value.environment_variables
}

module "monitoring" {
  for_each = module.lambda

  source = "../../modules/monitoring"

  function_name   = each.value.function_name
  alert_topic_arn = aws_sns_topic.alerts.arn
}
