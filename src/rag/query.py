"""Query handling: retrieve relevant chunks and generate grounded answers."""

import json
from typing import Any, Dict, List

import boto3
import psycopg2
from pgvector.psycopg2 import register_vector


def retrieve_chunks(
    question_embedding: List[float],
    question_text: str,
    top_k: int,
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
    use_hybrid: bool = True,
) -> List[Dict[str, Any]]:
    """Retrieve most relevant chunks using hybrid retrieval.

    Combines vector similarity with full-text search via reciprocal rank fusion.

    Args:
        question_embedding: Question embedding vector
        question_text: Question text for full-text search
        top_k: Number of chunks to retrieve
        db_host: Database host
        db_port: Database port
        db_name: Database name
        db_user: Database username
        db_password: Database password
        use_hybrid: Whether to use hybrid retrieval (default True)

    Returns:
        List of chunk dictionaries with metadata, sorted by combined score
    """
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
    )
    register_vector(conn)

    try:
        with conn.cursor() as cur:
            if not use_hybrid:
                # Vector-only retrieval
                cur.execute(
                    """
                    SELECT
                        document_id, page_number, chunk_index,
                        chunk_text, start_offset, end_offset,
                        metadata, embedding <=> %s::vector AS distance
                    FROM document_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (question_embedding, question_embedding, top_k),
                )

                results = []
                for row in cur.fetchall():
                    results.append({
                        "document_id": row[0],
                        "page_number": row[1],
                        "chunk_index": row[2],
                        "chunk_text": row[3],
                        "start_offset": row[4],
                        "end_offset": row[5],
                        "metadata": row[6],
                        "distance": float(row[7]),
                    })
                return results

            # Hybrid retrieval: get top 2*top_k from each method
            fetch_limit = top_k * 2

            # Vector similarity results
            cur.execute(
                """
                SELECT
                    id, document_id, page_number, chunk_index,
                    chunk_text, start_offset, end_offset, metadata
                FROM document_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (question_embedding, fetch_limit),
            )
            vector_results = {row[0]: (idx, row) for idx, row in enumerate(cur.fetchall())}

            # Full-text search results using websearch_to_tsquery for more flexible matching
            cur.execute(
                """
                SELECT
                    id, document_id, page_number, chunk_index,
                    chunk_text, start_offset, end_offset, metadata,
                    ts_rank(text_search, websearch_to_tsquery('english', %s)) AS rank
                FROM document_chunks
                WHERE text_search @@ websearch_to_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (question_text, question_text, fetch_limit),
            )
            text_results = {row[0]: (idx, row) for idx, row in enumerate(cur.fetchall())}

            # Reciprocal Rank Fusion (RRF)
            # Score = 1 / (k + rank), where k=60 is a constant
            k = 60
            chunk_scores = {}

            for chunk_id, (rank, row) in vector_results.items():
                chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + 1 / (k + rank + 1)

            for chunk_id, (rank, row) in text_results.items():
                chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + 1 / (k + rank + 1)

            # Get all unique chunks
            all_chunks = {}
            for chunk_id, (rank, row) in vector_results.items():
                all_chunks[chunk_id] = row
            for chunk_id, (rank, row) in text_results.items():
                if chunk_id not in all_chunks:
                    all_chunks[chunk_id] = row[:8]  # Exclude rank column

            # Sort by RRF score and take top_k
            sorted_chunks = sorted(
                chunk_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:top_k]

            results = []
            for chunk_id, score in sorted_chunks:
                row = all_chunks[chunk_id]
                results.append({
                    "document_id": row[1],
                    "page_number": row[2],
                    "chunk_index": row[3],
                    "chunk_text": row[4],
                    "start_offset": row[5],
                    "end_offset": row[6],
                    "metadata": row[7],
                    "rrf_score": score,
                })

            return results
    finally:
        conn.close()


def generate_answer(
    question: str,
    context_chunks: List[Dict[str, Any]],
    llm_model_id: str,
    region: str,
) -> Dict[str, Any]:
    """Generate answer with citations using Bedrock LLM.

    Args:
        question: User question
        context_chunks: Retrieved context chunks
        llm_model_id: Bedrock LLM model ID
        region: AWS region

    Returns:
        Dictionary with answer, citations, and token usage
    """
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    context_text = "\n\n".join([
        f"[{i+1}] (Source: {chunk['document_id']}, Page: {chunk['page_number']})\n{chunk['chunk_text']}"
        for i, chunk in enumerate(context_chunks)
    ])

    prompt = f"""You are a helpful assistant that answers questions based ONLY on the provided context.

Context passages (numbered for citation):
{context_text}

Instructions:
- Answer the question using ONLY information from the context
- Cite sources using [1], [2], etc. after each claim
- If the context doesn't contain enough information, respond with EXACTLY this sentence and nothing else: "I don't know based on the provided documents."
- Do NOT add citation numbers to a refusal
- Be precise and include relevant details with citations

Question: {question}

Answer:"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    })

    response = bedrock.invoke_model(
        modelId=llm_model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())

    answer_text = result["content"][0]["text"].strip()

    # If the answer is a refusal, return no citations
    if answer_text == "I don't know based on the provided documents.":
        citations = []
    else:
        citations = []
        for i, chunk in enumerate(context_chunks):
            citation_marker = f"[{i+1}]"
            if citation_marker in answer_text:
                citations.append({
                    "number": i + 1,
                    "source": chunk["document_id"],
                    "page": chunk["page_number"],
                    "snippet": chunk["chunk_text"][:200] + "..." if len(chunk["chunk_text"]) > 200 else chunk["chunk_text"],
                    "full_text": chunk["chunk_text"],
                })

    return {
        "answer": answer_text,
        "citations": citations,
        "token_usage": {
            "input_tokens": result["usage"]["input_tokens"],
            "output_tokens": result["usage"]["output_tokens"],
        },
    }


def query_rag(
    question: str,
    config: Dict[str, Any],
    db_credentials: Dict[str, str],
) -> Dict[str, Any]:
    """Query the RAG system: embed question, retrieve chunks, generate answer.

    Args:
        question: User question
        config: Configuration dictionary
        db_credentials: Database credentials

    Returns:
        Dictionary with answer, citations, and metadata
    """
    from .ingest import embed_text

    question_embedding = embed_text(
        question,
        config["embedding_model_id"],
        config["aws_region"],
    )

    chunks = retrieve_chunks(
        question_embedding,
        question,
        config.get("top_k", 10),
        config["db_host"],
        config.get("db_port", 5432),
        config.get("db_name", "ragdb"),
        db_credentials["username"],
        db_credentials["password"],
        config.get("use_hybrid_retrieval", True),
    )

    if not chunks:
        return {
            "answer": "I don't know based on the provided documents.",
            "citations": [],
            "token_usage": {"input_tokens": 0, "output_tokens": 0},
            "retrieved_chunks": 0,
        }

    result = generate_answer(
        question,
        chunks,
        config["llm_model_id"],
        config["aws_region"],
    )

    result["retrieved_chunks"] = len(chunks)
    return result
