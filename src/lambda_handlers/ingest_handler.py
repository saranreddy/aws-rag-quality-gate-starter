"""Lambda handler for document ingestion triggered by S3 uploads."""

import json
import os
from typing import Any, Dict

from rag.config import get_db_credentials
from rag.ingest import process_document


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle S3 event and process uploaded document.

    Args:
        event: S3 event notification
        context: Lambda context

    Returns:
        Response dictionary
    """
    region = context.invoked_function_arn.split(":")[3]

    config = {
        "aws_region": region,
        "db_host": os.environ["DB_HOST"],
        "db_port": int(os.environ.get("DB_PORT", "5432")),
        "db_name": os.environ.get("DB_NAME", "ragdb"),
        "db_secret_name": os.environ["DB_SECRET_NAME"],
        "embedding_model_id": os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
        "chunk_size": int(os.environ.get("CHUNK_SIZE", "512")),
        "chunk_overlap": int(os.environ.get("CHUNK_OVERLAP", "50")),
    }

    db_credentials = get_db_credentials(config["db_secret_name"], config["aws_region"])

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        print(f"Processing document: s3://{bucket}/{key}")

        try:
            result = process_document(bucket, key, config, db_credentials)
            print(f"Success: {json.dumps(result)}")
        except Exception as e:
            print(f"Error processing {key}: {str(e)}")
            raise

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Processing complete"}),
    }
