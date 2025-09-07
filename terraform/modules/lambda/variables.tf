variable "function_name" {
  description = "The name of the Lambda function."
  type        = string
}

variable "handler" {
  description = "The handler for the Lambda function."
  type        = string
}

variable "runtime" {
  description = "The runtime for the Lambda function."
  type        = string
}

variable "source_path" {
  description = "The path to the Lambda function's zip archive."
  type        = string
}

variable "role_arn" {
  description = "The ARN of the IAM role for the Lambda function."
  type        = string
}

variable "environment_variables" {
  description = "A map of environment variables for the Lambda function."
  type        = map(string)
  default     = {}
}

variable "memory_size" {
  description = "The memory size for the Lambda function."
  type        = number
  default     = 128
}

variable "timeout" {
  description = "The timeout for the Lambda function."
  type        = number
  default     = 30
}
