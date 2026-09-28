# Infrastructure Setup

This directory contains Terraform configuration for deploying the RAG quality gate system on AWS.

## Resources Created

### Networking
- **VPC**: Dedicated VPC with public and private subnets across 2 AZs
- **NAT Gateway**: For Lambda internet access (Bedrock API calls)
- **Security Groups**: Least-privilege network rules for Lambda and Aurora

### Storage
- **S3 Buckets**: 
  - `documents`: For PDF uploads (triggers ingest Lambda)
  - `artifacts`: For Lambda deployment packages
  - Both with versioning, encryption, and public access blocked

### Database
- **Aurora PostgreSQL Serverless v2**: With pgvector extension
  - Min capacity: 0.5 ACUs (does not scale below 0.5 ACU minimum)
  - Max capacity: 2 ACUs
  - Automatic backups enabled (7-day retention)
  - Credentials stored in Secrets Manager
  - HNSW indexing for fast cosine similarity search

### Compute
- **Lambda Functions**:
  - `ingest-processor`: Triggered by S3 uploads, extracts/chunks/embeds documents
  - `query-handler`: Handles API requests, retrieves chunks and generates answers
  - `db-init`: One-time initialization of database schema with pgvector
- **VPC Configuration**: Lambdas run in private subnets with database access

### API
- **API Gateway HTTP API**: REST endpoint for query requests
  - CORS enabled
  - Integrated with query Lambda
  - Access logging to CloudWatch

### Observability
- **CloudWatch Dashboard**: Metrics for Lambda invocations, latency, errors, Aurora usage, API Gateway
- **CloudWatch Alarms**:
  - Lambda errors > threshold
  - Query latency > 30 seconds
  - API Gateway 5XX errors > threshold
- **Log Groups**: Lambda and API Gateway logs (7-day retention)

### IAM
- **Lambda Execution Role**: With least-privilege policies for:
  - S3 read access
  - Secrets Manager access
  - Bedrock InvokeModel
  - CloudWatch Logs write
  - VPC network interfaces (ENI management)

## Prerequisites

- **AWS CLI** configured with credentials (`aws configure`)
- **Terraform** >= 1.0 installed
- **Bedrock Model Access**: Enable model access in AWS Bedrock console
  - Go to AWS Console → Bedrock → Model access
  - Request access to:
    - Amazon Titan Text Embeddings v2 (open access)
    - Anthropic Claude models (requires submitting the one-time Anthropic use-case form)

## Cost Estimate

Rough monthly costs for light usage (~1000 queries/month):

| Resource | Cost Estimate |
|----------|--------------|
| Aurora Serverless v2 (0.5-2 ACUs) | $40-160/month (scales with usage) |
| Lambda invocations | $1-2/month |
| NAT Gateway | $32/month + data transfer |
| S3 storage | $1-5/month (depends on document volume) |
| API Gateway | $1/million requests (~$0.01) |
| CloudWatch Logs | $1-2/month |
| **Estimated Total** | **$75-200/month** |

**Cost Drivers**:
- Aurora is the largest cost (especially at higher ACU usage)
- NAT Gateway has fixed monthly cost + data charges
- Lambda and API Gateway costs scale with usage

**Cost Optimization**:
- Aurora scales down to 0.5 ACU minimum (does not fully scale to zero)
- Set lower `db_max_capacity` to cap Aurora costs
- Lambda cold starts trade latency for cost (vs provisioned concurrency)
- Consider VPC endpoints to reduce NAT Gateway data transfer costs (see `enable_vpc_endpoints` variable)

**Unverified**: Aurora Serverless v2 minimum 0.5 ACU cost and data transfer rates could not be verified without deploying. Consult AWS pricing calculator for your specific usage patterns.

## Usage

### Step 1: Build Lambda Packages

Before deploying, build the Lambda deployment packages with dependencies:

```bash
# From the repository root
./scripts/build_lambdas.sh
```

This script:
- Installs Python dependencies (psycopg2-binary, pgvector, pypdf, etc.) into `infra/build/` directories
- Uses `--platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:` to ensure Lambda compatibility
- Creates separate packages for db_init, ingest, and query Lambdas

**Note**: Run this script any time you change Python dependencies.

### Step 2: Initialize

```bash
terraform init
```

### Step 3: Customize Variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your desired values
```

**Important**: Ensure you have Bedrock model access enabled (see Prerequisites) and you've run the build script.

### Step 4: Plan

```bash
terraform plan
```

Review the planned changes. Terraform will create ~50 resources.

### Step 5: Apply

```bash
terraform apply
```

Type `yes` when prompted. Deployment takes ~10-15 minutes (mostly Aurora cluster creation).

### Step 6: Get Outputs

```bash
terraform output
```

Copy these values to `config/config.yaml` in the repository root:

```yaml
aws_region: <region>
db_host: <db_host>
db_port: 5432
db_name: <db_name>
db_secret_name: <db_secret_name>
documents_bucket: <documents_bucket>
artifacts_bucket: <artifacts_bucket>
api_gateway_url: <api_gateway_url>
```

### Step 7: Test the Deployment

Upload a PDF to the documents bucket:

```bash
aws s3 cp test.pdf s3://$(terraform output -raw documents_bucket)/test.pdf
```

Check ingest Lambda logs:

```bash
aws logs tail /aws/lambda/$(terraform output -raw ingest_function_name) --follow
```

Query the API:

```bash
curl -X POST $(terraform output -raw query_endpoint) \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the main topic of the document?"}'
```

## Remote State

This starter includes commented-out S3 backend configuration in `main.tf`. To use remote state:

1. Create an S3 bucket and DynamoDB table (see [aws-terraform-remote-state-starter](https://github.com/saranreddy/aws-terraform-remote-state-starter))
2. Uncomment the `backend "s3"` block in `main.tf`
3. Run `terraform init` to migrate state

## Destroy Resources

To remove all infrastructure:

```bash
terraform destroy
```

**Warning**: This will delete the Aurora cluster, all S3 buckets (and their contents), and Lambda functions. Back up any important data first.

### Lambda ENI Cleanup Delay

Lambda functions in VPCs create Elastic Network Interfaces (ENIs) that can take 10-15 minutes to detach after function deletion. During `terraform destroy`, you may see:

```
aws_subnet.private[0]: Still destroying... [12m30s elapsed]
aws_security_group.lambda: Still destroying... [12m30s elapsed]
```

This is normal. Terraform will wait up to 45 minutes for ENIs to detach (configured via `timeouts` blocks).

**Optional faster cleanup**: Before running `terraform destroy`, you can manually delete "available" ENIs:

```bash
# Run from the scripts/ directory
./cleanup_enis.sh
```

This helper script identifies and deletes detached ENIs associated with the stack's security group, reducing destroy time to ~2-3 minutes.

## Modular Database Setup

The Aurora PostgreSQL configuration is designed to be modular. To swap it for a standalone module:

1. Replace `rds.tf` with:
   ```hcl
   module "aurora" {
     source = "path/to/aws-Aurora-Postgres-database-tf-module"
     # ... module variables
   }
   ```

2. Update references to `aws_rds_cluster.aurora` with `module.aurora.*`

## Troubleshooting

### Deployment Fails with "InvalidParameterException: DBCluster requires VPC"

Ensure the VPC and subnets are created before the Aurora cluster. This should be automatic with Terraform's dependency graph.

### Lambda Timeout Errors

- Increase `timeout` in `lambda.tf` (default: 300s for ingest, 60s for query)
- Check Lambda logs for specific errors

### Database Connection Failures

- Verify Lambda is in the same VPC as Aurora
- Check security group rules allow Lambda → Aurora on port 5432
- Confirm Secrets Manager secret contains correct credentials

### Bedrock Access Denied

- Enable model access in Bedrock console (see Prerequisites)
- Verify IAM role has `bedrock:InvokeModel` permission
- Check you're using the correct model IDs for your region

### High Costs

- Check Aurora ACU usage in CloudWatch
- Reduce `db_max_capacity` to cap Aurora costs
- Review NAT Gateway data transfer (largest non-Aurora cost)

## Security Notes

- All S3 buckets block public access
- Database credentials stored in Secrets Manager (never hardcoded)
- Lambdas use least-privilege IAM roles
- Aurora in private subnets (no public endpoint)
- All resources encrypted at rest (S3: AES256, Aurora: default AWS encryption)

## Outputs

After `terraform apply`, use `terraform output` to retrieve:

- `documents_bucket`: Upload PDFs here
- `query_endpoint`: POST requests with `{"question": "..."}`
- `cloudwatch_dashboard_url`: View metrics
- `db_secret_name`: For manual database access
