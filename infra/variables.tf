variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "rag-quality-gate"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "ragdb"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "ragadmin"
}

variable "embedding_model_id" {
  description = "Bedrock embedding model ID"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "llm_model_id" {
  description = "Bedrock LLM inference profile ID (requires Anthropic use-case form submission in Bedrock console)"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-6"
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "15.15"
}

variable "force_destroy_buckets" {
  description = "Allow Terraform to destroy S3 buckets with contents (set false for production)"
  type        = bool
  default     = true
}

variable "enable_vpc_endpoints" {
  description = "Enable VPC endpoints for Bedrock, S3, and Secrets Manager to avoid NAT Gateway costs"
  type        = bool
  default     = false
}

variable "chunk_size" {
  description = "Text chunk size in characters (structure-aware chunking with smaller focused chunks)"
  type        = number
  default     = 400
}

variable "chunk_overlap" {
  description = "Text chunk overlap in characters"
  type        = number
  default     = 50
}

variable "top_k" {
  description = "Number of chunks to retrieve for RAG (increased for better coverage)"
  type        = number
  default     = 10
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_min_capacity" {
  description = "Aurora Serverless v2 minimum capacity (ACUs)"
  type        = number
  default     = 0.5
}

variable "db_max_capacity" {
  description = "Aurora Serverless v2 maximum capacity (ACUs)"
  type        = number
  default     = 2
}
