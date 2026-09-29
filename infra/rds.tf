# Random password for database
resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Secrets Manager secret for database credentials
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${var.project_name}-db-credentials"
  recovery_window_in_days = 0

  tags = {
    Name = "RAG Database Credentials"
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db_password.result
    host     = aws_rds_cluster.aurora.endpoint
    port     = 5432
    dbname   = var.db_name
  })
}

# Aurora PostgreSQL Serverless v2 cluster
resource "aws_rds_cluster" "aurora" {
  cluster_identifier     = "${var.project_name}-aurora-cluster"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = var.aurora_engine_version
  database_name          = var.db_name
  master_username        = var.db_username
  master_password        = random_password.db_password.result
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  serverlessv2_scaling_configuration {
    min_capacity = var.db_min_capacity
    max_capacity = var.db_max_capacity
  }

  skip_final_snapshot = true

  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"

  enabled_cloudwatch_logs_exports = ["postgresql"]

  depends_on = [aws_cloudwatch_log_group.aurora_postgresql]

  tags = {
    Name = "RAG Aurora Cluster"
  }
}

# CloudWatch Log Group for Aurora PostgreSQL logs
resource "aws_cloudwatch_log_group" "aurora_postgresql" {
  name              = "/aws/rds/cluster/${var.project_name}-aurora-cluster/postgresql"
  retention_in_days = 7

  tags = {
    Name = "Aurora PostgreSQL Logs"
  }
}

# Aurora Serverless v2 instance
resource "aws_rds_cluster_instance" "aurora" {
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version

  tags = {
    Name = "RAG Aurora Instance"
  }
}

# Lambda function to initialize database schema
resource "aws_lambda_function" "db_init" {
  function_name = "${var.project_name}-db-init"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "db_init.handler"
  runtime       = "python3.11"
  timeout       = 60

  filename         = data.archive_file.db_init_package.output_path
  source_code_hash = data.archive_file.db_init_package.output_base64sha256

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      DB_SECRET_NAME = aws_secretsmanager_secret.db_credentials.name
    }
  }

  tags = {
    Name = "RAG Database Initialization"
  }

  depends_on = [aws_rds_cluster_instance.aurora]
}


# Invoke db init Lambda once to set up schema
resource "aws_lambda_invocation" "db_init" {
  function_name = aws_lambda_function.db_init.function_name

  input = jsonencode({
    action = "init"
  })

  depends_on = [
    aws_lambda_function.db_init,
    aws_secretsmanager_secret_version.db_credentials,
    aws_cloudwatch_log_group.db_init,
  ]
}
