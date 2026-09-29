#!/usr/bin/env python3
"""Cleanup Lambda ENIs during terraform destroy to speed up teardown.

This script runs in a loop checking for "available" (detached) ENIs and deleting them
as they become available during the destroy process. Lambda ENIs stay "in-use" until
~19 minutes into destroy, then transition to "available".

The script exits automatically when the security group is deleted (normal completion)
or after a timeout (default 45 minutes).

Usage:
    # In one terminal:
    terraform destroy

    # In another terminal (or same terminal before destroy):
    python scripts/cleanup_enis.py --watch

    # Or one-time cleanup before destroy:
    python scripts/cleanup_enis.py
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Error: boto3 not installed. Install with: pip install boto3")
    sys.exit(1)


def find_lambda_security_group(ec2_client, project_name):
    """Find the Lambda security group for the project."""
    try:
        response = ec2_client.describe_security_groups(
            Filters=[
                {"Name": "tag:Name", "Values": [f"{project_name}-lambda-sg"]}
            ]
        )
        if response["SecurityGroups"]:
            return response["SecurityGroups"][0]["GroupId"]
        return None
    except ClientError as e:
        print(f"Error finding security group: {e}")
        return None


def find_available_enis(ec2_client, sg_id):
    """Find ENIs attached to security group in 'available' state."""
    try:
        response = ec2_client.describe_network_interfaces(
            Filters=[
                {"Name": "group-id", "Values": [sg_id]},
                {"Name": "status", "Values": ["available"]}
            ]
        )
        return response["NetworkInterfaces"]
    except ClientError as e:
        print(f"Error finding ENIs: {e}")
        return []


def delete_eni(ec2_client, eni_id):
    """Delete a network interface."""
    try:
        ec2_client.delete_network_interface(NetworkInterfaceId=eni_id)
        return True
    except ClientError as e:
        if "does not exist" in str(e) or "InvalidNetworkInterfaceID.NotFound" in str(e):
            # Already deleted
            return True
        print(f"Error deleting ENI {eni_id}: {e}")
        return False


def cleanup_once(project_name, region):
    """Perform one-time ENI cleanup."""
    ec2 = boto3.client("ec2", region_name=region)

    print(f"Looking for Lambda ENIs for project '{project_name}' in region '{region}'...")

    sg_id = find_lambda_security_group(ec2, project_name)
    if not sg_id:
        print(f"No Lambda security group found for project '{project_name}'")
        return 0

    print(f"Found Lambda security group: {sg_id}")

    enis = find_available_enis(ec2, sg_id)
    if not enis:
        print("No available ENIs found to delete")
        return 0

    print(f"Found {len(enis)} available ENI(s)")

    deleted = 0
    for eni in enis:
        eni_id = eni["NetworkInterfaceId"]
        print(f"Deleting ENI: {eni_id}")
        if delete_eni(ec2, eni_id):
            deleted += 1

    print(f"Successfully deleted {deleted} ENI(s)")
    return deleted


def cleanup_watch(project_name, region, interval=30, timeout_minutes=45):
    """Watch for ENIs and delete them as they become available.

    Exits when:
    - The security group is deleted (normal completion during terraform destroy)
    - The timeout is reached (default 45 minutes to match Terraform's timeout)
    - Ctrl+C is pressed
    """
    ec2 = boto3.client("ec2", region_name=region)

    print(f"Watching for Lambda ENIs for project '{project_name}' in region '{region}'")
    print(f"Checking every {interval} seconds. Timeout: {timeout_minutes} minutes. Press Ctrl+C to stop.\n")

    sg_id = find_lambda_security_group(ec2, project_name)
    if not sg_id:
        print(f"No Lambda security group found for project '{project_name}'")
        return 0

    print(f"Found Lambda security group: {sg_id}\n")

    total_deleted = 0
    iteration = 0
    start_time = time.time()

    try:
        while True:
            iteration += 1
            elapsed_minutes = (time.time() - start_time) / 60

            if elapsed_minutes > timeout_minutes:
                print(f"\n[{time.strftime('%H:%M:%S')}] Timeout reached ({timeout_minutes} minutes)")
                print(f"Security group {sg_id} still exists but timeout exceeded.")
                print(f"Deleted {total_deleted} ENI(s) total.")
                return total_deleted

            # Check if security group still exists
            current_sg_id = find_lambda_security_group(ec2, project_name)
            if not current_sg_id:
                print(f"\n[{time.strftime('%H:%M:%S')}] Security group deleted - destroy complete!")
                print(f"Deleted {total_deleted} ENI(s) total.")
                return total_deleted

            enis = find_available_enis(ec2, sg_id)

            if enis:
                print(f"[{time.strftime('%H:%M:%S')}] Found {len(enis)} available ENI(s)")
                for eni in enis:
                    eni_id = eni["NetworkInterfaceId"]
                    print(f"  Deleting: {eni_id}")
                    if delete_eni(ec2, eni_id):
                        total_deleted += 1
            else:
                if iteration % 4 == 0:
                    print(f"[{time.strftime('%H:%M:%S')}] No available ENIs (checked {iteration} times, {elapsed_minutes:.1f} min elapsed)")

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\nStopped watching. Deleted {total_deleted} ENI(s) total.")
        return total_deleted


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup Lambda ENIs to speed up terraform destroy"
    )
    parser.add_argument(
        "--project-name",
        default=os.environ.get("PROJECT_NAME", "rag-quality-gate"),
        help="Project name (default: rag-quality-gate or $PROJECT_NAME)"
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region (default: us-east-1 or $AWS_REGION)"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode: continuously check and delete ENIs as they become available"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Check interval in seconds for watch mode (default: 30)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Timeout in minutes for watch mode (default: 45)"
    )

    args = parser.parse_args()

    if args.watch:
        cleanup_watch(args.project_name, args.region, args.interval, args.timeout)
    else:
        cleanup_once(args.project_name, args.region)


if __name__ == "__main__":
    main()
