output "documents_bucket" {
  description = "S3 bucket name for document uploads"
  value       = aws_s3_bucket.documents.id
}

output "artifacts_bucket" {
  description = "S3 bucket name for artifacts"
  value       = aws_s3_bucket.artifacts.id
}

output "db_host" {
  description = "Aurora cluster endpoint"
  value       = aws_rds_cluster.aurora.endpoint
}

output "db_port" {
  description = "Aurora database port"
  value       = aws_rds_cluster.aurora.port
}

output "db_name" {
  description = "Database name"
  value       = var.db_name
}

output "db_secret_name" {
  description = "Secrets Manager secret name for database credentials"
  value       = aws_secretsmanager_secret.db_credentials.name
}

output "ingest_function_name" {
  description = "Ingest Lambda function name"
  value       = aws_lambda_function.ingest.function_name
}

output "query_function_name" {
  description = "Query Lambda function name"
  value       = aws_lambda_function.query.function_name
}

output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "query_endpoint" {
  description = "Full query endpoint URL"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/query"
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "region" {
  description = "AWS region"
  value       = var.aws_region
}
