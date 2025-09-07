variable "aws_region" {
  description = "The AWS region to deploy the resources in."
  type        = string
  default     = "us-east-1"
}

variable "lambda_handler" {
  description = "The default handler for the lambda functions."
  type        = string
  default     = "main.handler"
}

variable "lambda_runtime" {
  description = "The default runtime for the lambda functions."
  type        = string
  default     = "python3.11"
}

variable "functions" {
  description = "A map of lambda functions to create."
  type = map(object({
    source_path = string
    memory_size = number
    timeout     = number
    environment_variables = map(string)
  }))
  default = {
    "ingest_function" = {
      source_path = "../../../../build/prod/ingest_function.zip"
      memory_size = 1024
      timeout     = 300
      environment_variables = {}
    },
    "query_function" = {
      source_path = "../../../../build/prod/query_function.zip"
      memory_size = 1024
      timeout     = 300
      environment_variables = {}
    },
    "openai_embedding_proxy" = {
      source_path = "../../../../build/prod/openai_embedding_proxy.zip"
      memory_size = 512
      timeout     = 120
      environment_variables = {}
    }
  }
}
