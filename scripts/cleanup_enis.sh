#!/bin/bash
# Cleanup Lambda ENIs before terraform destroy to speed up teardown
# This script deletes "available" (detached) ENIs associated with the stack's Lambda security group

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="${PROJECT_NAME:-rag-quality-gate}"
REGION="${AWS_REGION:-us-east-1}"

echo "Cleaning up Lambda ENIs for project: $PROJECT_NAME in region: $REGION"

# Get the Lambda security group ID
SG_ID=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters "Name=tag:Name,Values=${PROJECT_NAME}-lambda-sg" \
  --query 'SecurityGroups[0].GroupId' \
  --output text 2>/dev/null)

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  echo "No Lambda security group found for project $PROJECT_NAME"
  exit 0
fi

echo "Found Lambda security group: $SG_ID"

# Find all ENIs attached to this security group in "available" state
ENI_IDS=$(aws ec2 describe-network-interfaces \
  --region "$REGION" \
  --filters "Name=group-id,Values=$SG_ID" "Name=status,Values=available" \
  --query 'NetworkInterfaces[*].NetworkInterfaceId' \
  --output text)

if [ -z "$ENI_IDS" ]; then
  echo "No available ENIs found to delete"
  exit 0
fi

echo "Found available ENIs: $ENI_IDS"

# Delete each ENI
for ENI_ID in $ENI_IDS; do
  echo "Deleting ENI: $ENI_ID"
  aws ec2 delete-network-interface \
    --region "$REGION" \
    --network-interface-id "$ENI_ID" || echo "Failed to delete $ENI_ID (may already be deleted)"
done

echo "ENI cleanup complete!"
echo "You can now run 'terraform destroy' with reduced wait time"
