import os
from typing import List, Dict, Any
import logging
from dotenv import load_dotenv

# LangChain components
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.retrievers import PineconeHybridSearchRetriever
from langchain_huggingface import HuggingFaceEmbeddings

# Pinecone components
from pinecone import Pinecone, ServerlessSpec
from pinecone_text.sparse import BM25Encoder

# Document processing
from document_processor import DocumentProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class HybridRAGApp:
    """
    A comprehensive Hybrid RAG application with multi-file support,
    Pinecone vector storage, and OpenAI LLM integration.
    """

    def __init__(
        self,
        index_name: str = "hybrid-rag",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.5,
    ):
        """
        Initialize the Hybrid RAG application.

        Args:
            index_name: Name of the Pinecone index
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            model_name: OpenAI model name
            temperature: Temperature for LLM generation
        """
        self.index_name = index_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model_name = model_name
        self.temperature = temperature

        # Initialize components
        self._setup_pinecone()
        self._setup_embeddings()
        self._setup_bm25()
        self._setup_retriever()
        self._setup_llm()
        self._setup_prompt_template()

        # Initialize document processor
        self.doc_processor = DocumentProcessor(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

        logger.info("Hybrid RAG application initialized successfully")

    def _setup_pinecone(self):
        """Initialize Pinecone client and index."""
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY not found in environment variables")

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=api_key)

        # Create index if it doesn't exist
        if self.index_name not in [index.name for index in self.pc.list_indexes()]:
            logger.info(f"Creating Pinecone index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=384,  # Dimension for all-MiniLM-L6-v2
                metric="dotproduct",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )

        self.index = self.pc.Index(self.index_name)
        logger.info(f"Pinecone index '{self.index_name}' ready")

    def _setup_embeddings(self):
        """Initialize HuggingFace embeddings."""
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        logger.info("HuggingFace embeddings initialized")

    def _setup_bm25(self):
        """Initialize BM25 encoder."""
        self.bm25_encoder = BM25Encoder().default()
        logger.info("BM25 encoder initialized")

    def _setup_retriever(self):
        """Initialize hybrid search retriever."""
        self.retriever = PineconeHybridSearchRetriever(
            embeddings=self.embeddings,
            sparse_encoder=self.bm25_encoder,
            index=self.index,
        )
        logger.info("Hybrid search retriever initialized")

    def _setup_llm(self):
        """Initialize OpenAI LLM."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.llm = ChatOpenAI(
            model_name=self.model_name,
            temperature=self.temperature,
            openai_api_key=api_key,
        )
        logger.info(f"OpenAI LLM initialized with model: {self.model_name}")

    def _setup_prompt_template(self):
        """Setup the prompt template for RAG."""
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""
You are a helpful AI assistant that answers questions based on the provided context. 
Use only the information from the context to answer the question. If the context doesn't 
contain enough information to answer the question, say "I don't have enough information 
to answer this question based on the provided context."

Context:
{context}

Question: {question}

Answer:""",
        )

        self.llm_chain = LLMChain(llm=self.llm, prompt=self.prompt_template)
        logger.info("Prompt template and LLM chain initialized")

    def add_documents(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Process and add documents to the vector database.

        Args:
            file_paths: List of file paths to process

        Returns:
            Dictionary with processing results
        """
        all_documents = []
        processing_stats = {
            "total_files": len(file_paths),
            "successful_files": 0,
            "failed_files": 0,
            "total_chunks": 0,
            "errors": [],
        }

        for file_path in file_paths:
            try:
                if os.path.isfile(file_path):
                    documents = self.doc_processor.process_file(file_path)
                    all_documents.extend(documents)
                    processing_stats["successful_files"] += 1
                    processing_stats["total_chunks"] += len(documents)
                    logger.info(f"Successfully processed: {file_path}")
                elif os.path.isdir(file_path):
                    documents = self.doc_processor.process_directory(file_path)
                    all_documents.extend(documents)
                    processing_stats["successful_files"] += 1
                    processing_stats["total_chunks"] += len(documents)
                    logger.info(f"Successfully processed directory: {file_path}")
                else:
                    raise FileNotFoundError(f"Path not found: {file_path}")

            except Exception as e:
                processing_stats["failed_files"] += 1
                error_msg = f"Error processing {file_path}: {str(e)}"
                processing_stats["errors"].append(error_msg)
                logger.error(error_msg)
                continue

        if all_documents:
            # Add documents to the retriever
            texts = [doc.page_content for doc in all_documents]
            metadatas = [doc.metadata for doc in all_documents]

            try:
                # Use the retriever's add_texts method
                self.retriever.add_texts(texts, metadatas=metadatas)
                logger.info(f"Added {len(all_documents)} chunks to vector database")
            except Exception as e:
                logger.error(f"Error adding texts to retriever: {str(e)}")
                # Still return processing stats even if adding to retriever failed
                processing_stats["errors"].append(
                    f"Error adding to retriever: {str(e)}"
                )

        return processing_stats

    def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Query the RAG system with a question.

        Args:
            question: The question to ask
            top_k: Number of top documents to retrieve

        Returns:
            Dictionary with query results
        """
        try:
            # Retrieve relevant documents
            logger.info(f"Retrieving documents for question: {question}")
            retrieved_docs = self.retriever.get_relevant_documents(question, k=top_k)

            if not retrieved_docs:
                return {
                    "answer": "I don't have enough information to answer this question.",
                    "sources": [],
                    "retrieved_docs": [],
                    "question": question,
                }

            # Prepare context from retrieved documents
            context = "\n\n".join([doc.page_content for doc in retrieved_docs])

            # Generate answer using LLM
            logger.info("Generating answer using OpenAI LLM")
            response = self.llm_chain.run({"context": context, "question": question})

            # Prepare sources information
            sources = []
            for doc in retrieved_docs:
                source_info = {
                    "file_name": doc.metadata.get("file_name", "Unknown"),
                    "file_type": doc.metadata.get("file_type", "Unknown"),
                    "chunk_id": doc.metadata.get("chunk_id", "Unknown"),
                    "content_preview": doc.page_content[:200] + "..."
                    if len(doc.page_content) > 200
                    else doc.page_content,
                }
                sources.append(source_info)

            return {
                "answer": response,
                "sources": sources,
                "retrieved_docs": retrieved_docs,
                "question": question,
                "context_length": len(context),
            }

        except Exception as e:
            logger.error(f"Error during query: {str(e)}")
            return {
                "answer": f"An error occurred while processing your question: {str(e)}",
                "sources": [],
                "retrieved_docs": [],
                "question": question,
                "error": str(e),
            }

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the Pinecone index."""
        try:
            # Get index stats from Pinecone
            stats = self.index.describe_index_stats()

            # Convert to dictionary if it's not already
            if hasattr(stats, "__dict__"):
                stats_dict = stats.__dict__
            elif isinstance(stats, dict):
                stats_dict = stats
            else:
                # Try to access attributes directly
                stats_dict = {}
                for attr in [
                    "total_vector_count",
                    "dimension",
                    "index_fullness",
                    "namespaces",
                ]:
                    try:
                        if hasattr(stats, attr):
                            stats_dict[attr] = getattr(stats, attr)
                    except:
                        pass

            # Extract values with defaults
            total_vector_count = stats_dict.get("total_vector_count", 0)
            dimension = stats_dict.get("dimension", 384)
            index_fullness = stats_dict.get("index_fullness", 0)
            namespaces = stats_dict.get("namespaces", {})

            # If we couldn't get the values, try alternative methods
            if total_vector_count == 0:
                try:
                    # Try to get total vector count from namespaces
                    if namespaces:
                        total_vector_count = sum(namespaces.values())
                except:
                    pass

            return {
                "total_vector_count": total_vector_count,
                "dimension": dimension,
                "index_fullness": index_fullness,
                "namespaces": namespaces,
            }
        except Exception as e:
            logger.error(f"Error getting index stats: {str(e)}")
            return {
                "total_vector_count": 0,
                "dimension": 384,
                "index_fullness": 0,
                "namespaces": {},
                "error": str(e),
            }

    def clear_index(self):
        """Clear all vectors from the index."""
        try:
            self.index.delete(delete_all=True)
            logger.info("Index cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing index: {str(e)}")

    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats."""
        return self.doc_processor.get_supported_formats()
