variable "function_name" {
  description = "The name of the Lambda function to monitor."
  type        = string
}

variable "alert_topic_arn" {
  description = "The ARN of the SNS topic to send alerts to."
  type        = string
}
