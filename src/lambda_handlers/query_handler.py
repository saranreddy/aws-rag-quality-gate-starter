"""Lambda handler for query API via API Gateway."""

import json
import os
import time
from typing import Any, Dict

from rag.config import get_db_credentials
from rag.query import query_rag


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle query request from API Gateway.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    config = {
        "aws_region": os.environ["AWS_REGION"],
        "db_host": os.environ["DB_HOST"],
        "db_port": int(os.environ.get("DB_PORT", "5432")),
        "db_name": os.environ.get("DB_NAME", "ragdb"),
        "db_secret_name": os.environ["DB_SECRET_NAME"],
        "embedding_model_id": os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
        "llm_model_id": os.environ.get("LLM_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
        "top_k": int(os.environ.get("TOP_K", "5")),
    }
    
    try:
        body = json.loads(event.get("body", "{}"))
        question = body.get("question")
        
        if not question:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing 'question' in request body"}),
            }
        
        db_credentials = get_db_credentials(config["db_secret_name"], config["aws_region"])
        
        result = query_rag(question, config, db_credentials)
        
        latency_ms = (time.time() - start_time) * 1000
        
        result["latency_ms"] = latency_ms
        
        print(json.dumps({
            "metric": "query",
            "latency_ms": latency_ms,
            "input_tokens": result["token_usage"]["input_tokens"],
            "output_tokens": result["token_usage"]["output_tokens"],
            "retrieved_chunks": result["retrieved_chunks"],
        }))
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }
