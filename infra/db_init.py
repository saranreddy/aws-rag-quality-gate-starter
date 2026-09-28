"""Lambda function to initialize database schema with pgvector extension."""

import json
import os

import boto3
import psycopg2


def get_db_credentials(secret_name, region):
    """Get database credentials from Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


def handler(event, context):
    """Initialize database schema."""
    secret_name = os.environ["DB_SECRET_NAME"]
    region = context.invoked_function_arn.split(":")[3]

    credentials = get_db_credentials(secret_name, region)

    conn = psycopg2.connect(
        host=credentials["host"],
        port=credentials["port"],
        dbname=credentials["dbname"],
        user=credentials["username"],
        password=credentials["password"],
    )

    try:
        with conn.cursor() as cur:
            # Enable pgvector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # Create document_chunks table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id SERIAL PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_offset INTEGER NOT NULL,
                    embedding vector(1024),
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create index on embedding for fast similarity search using HNSW
            cur.execute("""
                CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
                ON document_chunks
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """)

            # Create index on document_id for filtering
            cur.execute("""
                CREATE INDEX IF NOT EXISTS document_chunks_document_id_idx
                ON document_chunks (document_id);
            """)

        conn.commit()

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Database initialized successfully"})
        }

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
