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
  description = "Bedrock LLM model ID"
  type        = string
  default     = "anthropic.claude-3-5-sonnet-20241022-v2:0"
}

variable "chunk_size" {
  description = "Text chunk size in characters"
  type        = number
  default     = 512
}

variable "chunk_overlap" {
  description = "Text chunk overlap in characters"
  type        = number
  default     = 50
}

variable "top_k" {
  description = "Number of chunks to retrieve for RAG"
  type        = number
  default     = 5
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
