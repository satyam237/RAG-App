import os
from dotenv import load_dotenv
from langchain_community.retrievers import PineconeHybridSearchRetriever
from pinecone import Pinecone, ServerlessSpec
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone_text.sparse import BM25Encoder

load_dotenv()
api_key = os.getenv("PINECONE_API_KEY")

# Initialize Pinecone client
pc = Pinecone(api_key=api_key)

index_name = "hybrid-rag"

if index_name not in [index.name for index in pc.list_indexes()]:
    pc.create_index(
        name=index_name,
        dimension=384,
        metric="dotproduct",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

index = pc.Index(index_name)
index

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
embeddings

bm25_encoder = BM25Encoder().default()
bm25_encoder

sentences = [
    "The quick brown fox jumps over the lazy dog",
    "In 2024 I visited New York.",
    "I love to eat pizza",
    "I love to drink Cold Coffee",
]

bm25_encoder.fit(sentences)

bm25_encoder.dump("bm25_values.json")

bm25_encoder = BM25Encoder().load("bm25_values.json")

retriever = PineconeHybridSearchRetriever(
    embeddings=embeddings, sparse_encoder=bm25_encoder, index=index
)
retriever

retriever.add_texts(sentences)

retriever.invoke("What is my favourite Drink.?")

"""
ENHANCED VERSION COMPARISON:

The original implementation above was a basic proof-of-concept that only handled:
- Simple sentences
- Basic hybrid search
- No document processing
- No LLM integration
- No multi-file support

The enhanced application now includes:

1. MULTI-FILE SUPPORT:
   - PDF, DOC, DOCX, PPTX, Images, CSV, TXT
   - Intelligent text extraction and OCR
   - Proper chunking with overlap

2. COMPREHENSIVE RAG PIPELINE:
   - DocumentProcessor class for multi-format handling
   - HybridRAGApp class for complete RAG functionality
   - OpenAI LLM integration with prompt templates
   - Source attribution and metadata tracking

3. USER INTERFACE:
   - Streamlit web application
   - File upload and processing
   - Interactive querying
   - Chat history and source tracking

4. ENTERPRISE FEATURES:
   - Configuration management
   - Error handling and logging
   - Index management and statistics
   - Batch processing capabilities

5. ENHANCED FUNCTIONALITY:
   - Recursive text splitting
   - Metadata preservation
   - Context-aware responses
   - Performance optimization

To use the enhanced version:
1. Run: streamlit run streamlit_app.py
2. Or use: python example_usage.py
3. Or import: from hybrid_rag_app import HybridRAGApp

The enhanced version transforms this simple script into a production-ready
RAG application with enterprise-level features and multi-file support.
"""
