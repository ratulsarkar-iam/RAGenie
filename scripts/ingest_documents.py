#!/usr/bin/env python3
"""CLI script for ingesting documents into the RAG system."""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.loader import load_config
from src.core.logging_config import setup_logging
from src.rag.page_index_store import PageIndexStore
from src.rag.chunker import DocumentChunker
from src.ingestion.pipeline import IngestionPipeline


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into the RAG system")
    parser.add_argument(
        "paths",
        nargs="+",
        help="File or directory paths to ingest"
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Recursively search directories"
    )
    parser.add_argument(
        "--config",
        "-c",
        default="config/config.yaml",
        help="Path to configuration file"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Setup logging
    logger = setup_logging(config.logging)
    logger.info("Starting document ingestion")
    
    # Initialize components
    store = PageIndexStore(config.rag.index_path)
    store.load()
    
    chunker = DocumentChunker(config.rag)
    pipeline = IngestionPipeline(store, chunker)
    
    # Process each path
    total_ingested = 0
    
    for path_str in args.paths:
        path = Path(path_str)
        
        if not path.exists():
            logger.error(f"Path does not exist: {path_str}")
            continue
        
        if path.is_file():
            try:
                pipeline.ingest_file(str(path))
                total_ingested += 1
            except Exception as e:
                logger.error(f"Failed to ingest {path_str}: {str(e)}")
        
        elif path.is_dir():
            docs = pipeline.ingest_directory(str(path), recursive=args.recursive)
            total_ingested += len(docs)
    
    # Print statistics
    stats = pipeline.get_ingestion_stats()
    
    print("\n" + "="*60)
    print("INGESTION COMPLETE")
    print("="*60)
    print(f"Total documents: {stats['total_documents']}")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Total size: {stats['total_size_bytes']:,} bytes")
    print(f"\nDocuments by type:")
    for file_type, count in stats['file_types'].items():
        print(f"  {file_type}: {count}")
    print("="*60)
    
    logger.info("Document ingestion completed")


if __name__ == "__main__":
    main()
