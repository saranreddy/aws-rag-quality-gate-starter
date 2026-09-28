"""Document ingestion: extract, chunk, embed, and store in pgvector."""

import json
import os
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import unquote_plus

import boto3
import psycopg2
from pgvector.psycopg2 import register_vector


def extract_text_from_pdf(pdf_path: str) -> List[Tuple[str, int]]:
    """Extract text from PDF with page numbers.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of (text, page_number) tuples
    """
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        pages.append((text, i + 1))
    return pages


def extract_text_from_text_file(file_path: str) -> List[Tuple[str, int]]:
    """Extract text from plain text or markdown file.

    Args:
        file_path: Path to text or markdown file

    Returns:
        List of (text, page_number) tuples (page 1 for text files)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    return [(text, 1)]


def chunk_text(text: str, chunk_size: int = 400, chunk_overlap: int = 50) -> List[Tuple[str, int, int]]:
    """Split text into chunks using structure-aware segmentation.

    Prioritizes natural document structure:
    1. Markdown headings (# ## ###)
    2. FAQ Q:/A: pairs
    3. Sentence boundaries with target chunk size

    Args:
        text: Input text
        chunk_size: Target chunk size in characters (smaller default for focused chunks)
        chunk_overlap: Overlap between chunks in characters

    Returns:
        List of (chunk_text, start_offset, end_offset) tuples
    """
    if not text:
        return []

    chunks = []

    # Split on markdown headings and FAQ Q:/A: pairs
    # Pattern matches markdown headings or Q:/A: pairs (keep them together)
    heading_pattern = re.compile(r'^#{1,6}\s+.+?$', re.MULTILINE)
    faq_pair_pattern = re.compile(r'^Q:\s*.+?\n+A:\s*.+?(?=\n\n|$)', re.MULTILINE | re.DOTALL)

    # Find all structural elements
    headings = [(m.start(), m.end(), 'heading') for m in heading_pattern.finditer(text)]
    faq_pairs = [(m.start(), m.end(), 'faq') for m in faq_pair_pattern.finditer(text)]

    # Combine and sort all boundaries
    all_boundaries = sorted(headings + faq_pairs, key=lambda x: x[0])

    if not all_boundaries:
        # No structure found, fall back to sentence-based chunking
        return _chunk_by_sentences(text, chunk_size, chunk_overlap, 0)

    # Process each structural section
    section_start = 0
    for i, (boundary_start, boundary_end, boundary_type) in enumerate(all_boundaries):
        # Check if there's text before this boundary
        if boundary_start > section_start:
            before_text = text[section_start:boundary_start].strip()
            if before_text:
                section_chunks = _chunk_by_sentences(before_text, chunk_size, chunk_overlap, section_start)
                chunks.extend(section_chunks)

        # Get the structural element
        element_text = text[boundary_start:boundary_end].strip()

        # For FAQ pairs, we already have Q+A together
        # For headings, get content until next boundary
        if boundary_type == 'faq':
            section_text = element_text
            next_section_start = boundary_end
        else:  # heading
            next_boundary_start = all_boundaries[i + 1][0] if i + 1 < len(all_boundaries) else len(text)
            content_text = text[boundary_end:next_boundary_start].strip()
            section_text = f"{element_text}\n{content_text}" if content_text else element_text
            next_section_start = next_boundary_start

        # If section is small enough, keep as single chunk
        if len(section_text) <= chunk_size * 1.5:
            chunks.append((section_text, boundary_start, boundary_end if boundary_type == 'faq' else next_section_start))
        else:
            # Section too large, split but try to keep structure together
            section_chunks = _chunk_by_sentences(section_text, chunk_size, chunk_overlap, boundary_start)
            chunks.extend(section_chunks)

        section_start = next_section_start

    # Handle any remaining text after last boundary
    if section_start < len(text):
        remaining = text[section_start:].strip()
        if remaining:
            remaining_chunks = _chunk_by_sentences(remaining, chunk_size, chunk_overlap, section_start)
            chunks.extend(remaining_chunks)

    return chunks


def _chunk_by_sentences(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    offset: int
) -> List[Tuple[str, int, int]]:
    """Helper function to chunk text by sentences.

    Args:
        text: Text to chunk
        chunk_size: Target size
        chunk_overlap: Overlap size
        offset: Starting offset in original document

    Returns:
        List of (chunk_text, start_offset, end_offset) tuples
    """
    if not text:
        return []

    # Split on sentence boundaries
    sentence_endings = re.compile(r'(?<=[.!?])\s+|\n+')
    sentences = [s.strip() for s in sentence_endings.split(text) if s.strip()]

    if not sentences:
        return [(text, offset, offset + len(text))]

    chunks = []
    current_chunk = []
    current_length = 0
    chunk_start = offset

    for sentence in sentences:
        sentence_len = len(sentence)

        # If adding this sentence exceeds chunk_size and we have content, finalize
        if current_length + sentence_len > chunk_size and current_chunk:
            chunk_content = ' '.join(current_chunk)
            chunk_end = chunk_start + len(chunk_content)
            chunks.append((chunk_content, chunk_start, chunk_end))

            # Overlap: keep sentences from end that fit in overlap
            overlap_length = 0
            overlap_sentences = []
            for sent in reversed(current_chunk):
                if overlap_length + len(sent) <= chunk_overlap:
                    overlap_sentences.insert(0, sent)
                    overlap_length += len(sent) + 1
                else:
                    break

            current_chunk = overlap_sentences
            current_length = overlap_length
            chunk_start = chunk_end - overlap_length

        current_chunk.append(sentence)
        current_length += sentence_len + 1

    # Final chunk
    if current_chunk:
        chunk_content = ' '.join(current_chunk)
        chunk_end = chunk_start + len(chunk_content)
        chunks.append((chunk_content, chunk_start, chunk_end))

    return chunks


def embed_text(text: str, model_id: str, region: str) -> List[float]:
    """Generate embedding using Amazon Bedrock.

    Args:
        text: Text to embed
        model_id: Bedrock model ID (e.g., amazon.titan-embed-text-v2:0)
        region: AWS region

    Returns:
        Embedding vector as list of floats
    """
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    body = json.dumps({"inputText": text})
    response = bedrock.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    return result["embedding"]


def store_chunks(
    chunks: List[Dict[str, Any]],
    document_id: str,
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
) -> None:
    """Store document chunks with embeddings in PostgreSQL.

    Deletes existing chunks for the document_id before inserting new ones.

    Args:
        chunks: List of chunk dictionaries with text, embedding, and metadata
        document_id: Document identifier to delete/replace
        db_host: Database host
        db_port: Database port
        db_name: Database name
        db_user: Database username
        db_password: Database password
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
            # Delete existing chunks for this document to avoid duplicates on re-ingest
            cur.execute(
                "DELETE FROM document_chunks WHERE document_id = %s",
                (document_id,)
            )

            for chunk in chunks:
                cur.execute(
                    """
                    INSERT INTO document_chunks (
                        document_id, page_number, chunk_index,
                        chunk_text, start_offset, end_offset,
                        embedding, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        chunk["document_id"],
                        chunk["page_number"],
                        chunk["chunk_index"],
                        chunk["chunk_text"],
                        chunk["start_offset"],
                        chunk["end_offset"],
                        chunk["embedding"],
                        json.dumps(chunk["metadata"]),
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def process_document(
    s3_bucket: str,
    s3_key: str,
    config: Dict[str, Any],
    db_credentials: Dict[str, str],
) -> Dict[str, Any]:
    """Process a document: download, extract, chunk, embed, and store.

    Args:
        s3_bucket: S3 bucket name
        s3_key: S3 object key (URL-encoded from S3 event)
        config: Configuration dictionary
        db_credentials: Database credentials

    Returns:
        Processing result summary
    """
    # URL-decode the S3 key (S3 events deliver URL-encoded keys)
    s3_key = unquote_plus(s3_key)

    s3 = boto3.client("s3", region_name=config["aws_region"])

    local_path = f"/tmp/{os.path.basename(s3_key)}"
    s3.download_file(s3_bucket, s3_key, local_path)

    # Determine file type and extract text accordingly
    file_ext = os.path.splitext(s3_key)[1].lower()
    if file_ext == '.pdf':
        pages = extract_text_from_pdf(local_path)
    elif file_ext in ['.txt', '.md']:
        pages = extract_text_from_text_file(local_path)
    else:
        raise ValueError(f"Unsupported file type: {file_ext}. Supported types: .pdf, .txt, .md")

    all_chunks = []
    chunk_index = 0

    for page_text, page_num in pages:
        page_chunks = chunk_text(
            page_text,
            chunk_size=config.get("chunk_size", 512),
            chunk_overlap=config.get("chunk_overlap", 50),
        )

        for text_chunk, start_offset, end_offset in page_chunks:
            embedding = embed_text(
                text_chunk,
                config["embedding_model_id"],
                config["aws_region"],
            )

            all_chunks.append({
                "document_id": s3_key,
                "page_number": page_num,
                "chunk_index": chunk_index,
                "chunk_text": text_chunk,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "embedding": embedding,
                "metadata": {
                    "source": s3_key,
                    "bucket": s3_bucket,
                },
            })
            chunk_index += 1

    store_chunks(
        all_chunks,
        s3_key,
        config["db_host"],
        config.get("db_port", 5432),
        config.get("db_name", "ragdb"),
        db_credentials["username"],
        db_credentials["password"],
    )

    os.remove(local_path)

    return {
        "document_id": s3_key,
        "total_chunks": len(all_chunks),
        "pages_processed": len(pages),
        "status": "success",
    }
