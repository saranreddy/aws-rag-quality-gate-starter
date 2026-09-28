"""RAG core functionality: ingest, query, and evaluation."""

from .config import load_config
from .ingest import process_document
from .query import query_rag

__all__ = ["process_document", "query_rag", "load_config"]
