# Package Lambda functions
# Note: Run scripts/build_lambdas.sh before terraform apply to build dependencies

data "archive_file" "db_init_package" {
  type        = "zip"
  output_path = "${path.module}/.terraform/db_init_package.zip"
  source_dir  = "${path.module}/build/db_init"
}

data "archive_file" "ingest_package" {
  type        = "zip"
  output_path = "${path.module}/.terraform/ingest_package.zip"
  source_dir  = "${path.module}/build/ingest"
}

data "archive_file" "query_package" {
  type        = "zip"
  output_path = "${path.module}/.terraform/query_package.zip"
  source_dir  = "${path.module}/build/query"
}

# Ingest Lambda function
resource "aws_lambda_function" "ingest" {
  function_name = "${var.project_name}-ingest-processor"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.ingest_handler.handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  filename         = data.archive_file.ingest_package.output_path
  source_code_hash = data.archive_file.ingest_package.output_base64sha256

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DB_HOST            = aws_rds_cluster.aurora.endpoint
      DB_PORT            = "5432"
      DB_NAME            = var.db_name
      DB_SECRET_NAME     = aws_secretsmanager_secret.db_credentials.name
      EMBEDDING_MODEL_ID = var.embedding_model_id
      CHUNK_SIZE         = tostring(var.chunk_size)
      CHUNK_OVERLAP      = tostring(var.chunk_overlap)
    }
  }

  tags = {
    Name = "RAG Ingest Processor"
  }
}

# Permission for S3 to invoke ingest Lambda
resource "aws_lambda_permission" "s3_invoke_ingest" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.documents.arn
}

# Query Lambda function
resource "aws_lambda_function" "query" {
  function_name = "${var.project_name}-query-handler"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handlers.query_handler.handler"
  runtime       = "python3.11"
  timeout       = 60
  memory_size   = 512

  filename         = data.archive_file.query_package.output_path
  source_code_hash = data.archive_file.query_package.output_base64sha256

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DB_HOST               = aws_rds_cluster.aurora.endpoint
      DB_PORT               = "5432"
      DB_NAME               = var.db_name
      DB_SECRET_NAME        = aws_secretsmanager_secret.db_credentials.name
      EMBEDDING_MODEL_ID    = var.embedding_model_id
      LLM_MODEL_ID          = var.llm_model_id
      TOP_K                 = tostring(var.top_k)
      USE_HYBRID_RETRIEVAL  = tostring(var.use_hybrid_retrieval)
    }
  }

  tags = {
    Name = "RAG Query Handler"
  }
}

# Permission for API Gateway to invoke query Lambda
resource "aws_lambda_permission" "api_invoke_query" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/aws/lambda/${aws_lambda_function.ingest.function_name}"
  retention_in_days = 7

  tags = {
    Name = "RAG Ingest Logs"
  }
}

resource "aws_cloudwatch_log_group" "query" {
  name              = "/aws/lambda/${aws_lambda_function.query.function_name}"
  retention_in_days = 7

  tags = {
    Name = "RAG Query Logs"
  }
}

resource "aws_cloudwatch_log_group" "db_init" {
  name              = "/aws/lambda/${aws_lambda_function.db_init.function_name}"
  retention_in_days = 7

  tags = {
    Name = "RAG DB Init Logs"
  }
}
