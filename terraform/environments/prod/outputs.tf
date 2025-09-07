output "lambda_functions" {
  description = "The created Lambda functions."
  value = {
    for k, v in module.lambda : k => {
      name = v.function_name
      arn  = v.function_arn
    }
  }
}

output "alerts_sns_topic_arn" {
  description = "The ARN of the SNS topic for alerts."
  value       = aws_sns_topic.alerts.arn
}
