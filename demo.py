#!/usr/bin/env python3
"""Demo script for the RAG Chatbot MVP."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.loader import load_config
from src.core.logging_config import setup_logging, get_logger
from src.llm.langchain_wrapper import LangChainLLM
from src.rag.page_index_store import PageIndexStore
from src.search.search_service import SearchService
from src.chat.orchestrator import ChatOrchestrator


def main():
    print("="*60)
    print("RAG CHATBOT MVP - DEMO")
    print("="*60)
    print()
    
    # Load configuration
    print("Loading configuration...")
    config = load_config()
    
    # Setup logging
    logger = setup_logging(config.logging)
    logger.info("Starting RAG Chatbot Demo")
    
    # Initialize RAG store
    print("Loading RAG index...")
    rag_store = PageIndexStore(config.rag.index_path)
    rag_store.load()
    
    stats = rag_store.get_stats()
    print(f"  - Documents: {stats['num_documents']}")
    print(f"  - Chunks: {stats['num_chunks']}")
    print()
    
    # Initialize LLM
    print("Loading LLM model (this may take a few minutes)...")
    print(f"  - Model: {config.llm.model_name}")
    print(f"  - Quantization: {config.llm.quantization}")
    print(f"  - Device: {config.llm.device}")
    
    llm_wrapper = LangChainLLM(config.llm)
    llm_wrapper.initialize()
    print("  - Model loaded successfully!")
    print()
    
    # Initialize search service
    print("Initializing search service...")
    search_service = SearchService(config.search)
    print(f"  - Provider: {config.search.provider}")
    print()
    
    # Initialize chat orchestrator
    print("Creating chat orchestrator...")
    orchestrator = ChatOrchestrator(
        llm_wrapper=llm_wrapper,
        rag_store=rag_store,
        search_service=search_service,
        max_history=config.conversation.max_history
    )
    
    # Start conversation
    orchestrator.start_conversation("demo-session")
    print("  - Chat orchestrator ready!")
    print()
    
    print("="*60)
    print("CHATBOT READY - Enter your questions (type 'quit' to exit)")
    print("="*60)
    print()
    
    # Interactive chat loop
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break
            
            # Special commands
            if user_input.lower() == 'clear':
                orchestrator.clear_conversation()
                print("Conversation cleared.\n")
                continue
            
            if user_input.lower() == 'history':
                history = orchestrator.get_conversation_history()
                print("\nConversation History:")
                for msg in history:
                    print(f"  {msg['role']}: {msg['content'][:100]}...")
                print()
                continue
            
            if user_input.lower() == 'stats':
                stats = rag_store.get_stats()
                print(f"\nRAG Statistics:")
                print(f"  Documents: {stats['num_documents']}")
                print(f"  Chunks: {stats['num_chunks']}")
                print()
                continue
            
            # Generate response (using simple mode for faster responses)
            print("\nAssistant: ", end="", flush=True)
            response = orchestrator.chat_simple(user_input)
            print(response)
            print()
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {str(e)}\n")
            logger.error(f"Demo error: {str(e)}", exc_info=True)
    
    # Cleanup
    print("\nCleaning up...")
    llm_wrapper.cleanup()
    print("Done!")


if __name__ == "__main__":
    main()
