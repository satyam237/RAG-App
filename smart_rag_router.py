import os
import logging
from typing import Dict, Any, List, Literal
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

# Web search - Tavily
from tavily import TavilyClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryClassification(BaseModel):
    """Structured output for query classification."""

    classification: Literal["GENERAL", "WEBSEARCH", "VECTORSTORE", "VAGUE_DOCUMENT"] = (
        Field(
            description="The classification of the query based on its intent and content"
        )
    )
    reasoning: str = Field(
        description="Detailed reasoning for why this classification was chosen"
    )
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0 for this classification",
        ge=0.0,
        le=1.0,
    )


class QueryClassifier:
    """LLM-based query classifier using OpenAI function calling."""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def classify_query(self, query: str) -> QueryClassification:
        """Classify a query using LLM-based reasoning."""

        # Define the classification function with correct format
        classification_function = {
            "type": "function",
            "function": {
                "name": "classify_query",
                "description": "Classify a user query to determine the best processing method",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "classification": {
                            "type": "string",
                            "enum": [
                                "GENERAL",
                                "WEBSEARCH",
                                "VECTORSTORE",
                                "VAGUE_DOCUMENT",
                            ],
                            "description": "The classification of the query",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Detailed reasoning for the classification",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence score for this classification",
                        },
                    },
                    "required": ["classification", "reasoning", "confidence"],
                },
            },
        }

        # Create the classification prompt
        classification_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert query classifier for an Adaptive RAG system. 
                    Your job is to classify user queries into one of four categories:

                    GENERAL: Simple greetings, casual conversation, personal questions, or queries that don't require specific knowledge.
                    Examples: "hi", "hello", "how are you", "who am i", "what's the weather like"

                    WEBSEARCH: Queries about current events, recent information, or topics that require up-to-date knowledge.
                    Examples: "latest news about AI", "recent developments in quantum computing", "current stock prices"

                    VECTORSTORE: Queries that should be answered using uploaded documents and local knowledge.
                    Examples: "what does the document say about", "summarize the uploaded files", "find information in my documents", 
                    "explain the model architecture from the PDF", "what does the paper say about", "analyze the document"

                    VAGUE_DOCUMENT: Queries that mention documents but are too vague to process effectively.
                    Examples: "help me with my documents", "answer questions about my files", "tell me about my docs"

                    Be confident in your classification and provide clear reasoning.""",
                ),
                ("human", "{query}"),
            ]
        )

        try:
            # Get classification using function calling
            response = self.llm.invoke(
                classification_prompt.format(query=query),
                tools=[classification_function],
                tool_choice={
                    "type": "function",
                    "function": {"name": "classify_query"},
                },
            )

            # Extract the classification from the response
            if response.tool_calls and len(response.tool_calls) > 0:
                tool_call = response.tool_calls[0]
                args = tool_call["args"]

                return QueryClassification(
                    classification=args["classification"],
                    reasoning=args["reasoning"],
                    confidence=args["confidence"],
                )
            else:
                # Fallback to keyword-based classification
                return self._fallback_classification(query)

        except Exception as e:
            logger.error(f"Error in LLM classification: {str(e)}")
            return self._fallback_classification(query)

    def _fallback_classification(self, query: str) -> QueryClassification:
        """Fallback keyword-based classification with improved document detection."""
        query_lower = query.lower().strip()

        # General conversation patterns
        general_patterns = [
            "hi",
            "hello",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "how are you",
            "what's up",
            "who am i",
            "what am i",
            "tell me about yourself",
            "thanks",
            "thank you",
            "bye",
            "goodbye",
            "see you",
        ]

        # Web search patterns
        websearch_patterns = [
            "latest",
            "recent",
            "news",
            "current",
            "today",
            "yesterday",
            "this week",
            "stock price",
            "weather",
            "covid",
            "election",
            "breaking news",
        ]

        # Vague document patterns
        vague_document_patterns = [
            "my documents",
            "my files",
            "my docs",
            "the documents",
            "the files",
            "help me with",
            "answer questions about",
            "tell me about my",
        ]

        # Document-specific patterns (should go to VECTORSTORE)
        document_patterns = [
            "pdf",
            "document",
            "paper",
            "research",
            "article",
            "text",
            "content",
            "information",
            "data",
            "file",
            "upload",
            "explain",
            "analyze",
            "summarize",
            "what does",
            "what is",
            "how does",
            "describe",
            "tell me about",
            "find",
            "search",
            "extract",
            "identify",
            "compare",
            "contrast",
            "discuss",
            "examine",
            "review",
            "study",
            "investigate",
            "explore",
            "understand",
            "learn about",
            "get information",
            "retrieve",
            "obtain",
            "access",
            "read",
            "parse",
            "process",
            "architecture",
            "model",
            "mechanism",
            "part",
            "section",
            "chapter",
            "figure",
            "table",
            "diagram",
        ]

        # Check patterns in order of priority
        for pattern in general_patterns:
            if pattern in query_lower:
                return QueryClassification(
                    classification="GENERAL",
                    reasoning=f"Query contains general conversation pattern: '{pattern}'",
                    confidence=0.8,
                )

        for pattern in websearch_patterns:
            if pattern in query_lower:
                return QueryClassification(
                    classification="WEBSEARCH",
                    reasoning=f"Query contains web search pattern: '{pattern}'",
                    confidence=0.8,
                )

        for pattern in vague_document_patterns:
            if pattern in query_lower:
                return QueryClassification(
                    classification="VAGUE_DOCUMENT",
                    reasoning=f"Query contains vague document reference: '{pattern}'",
                    confidence=0.7,
                )

        # Check for document-specific patterns (highest priority for document queries)
        for pattern in document_patterns:
            if pattern in query_lower:
                return QueryClassification(
                    classification="VECTORSTORE",
                    reasoning=f"Query contains document-related pattern: '{pattern}'",
                    confidence=0.8,
                )

        # Default to general for unknown queries
        return QueryClassification(
            classification="GENERAL",
            reasoning="Query does not match specific patterns, defaulting to general conversation",
            confidence=0.5,
        )


class AdaptiveRAGRouter:
    """Adaptive RAG Router with LLM-based query classification and intelligent routing."""

    def __init__(self, rag_app=None):
        """Initialize the Adaptive RAG Router."""
        self.rag_app = rag_app

        # Initialize OpenAI LLM
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.5,
            openai_api_key=api_key,
        )

        # Initialize query classifier
        self.query_classifier = QueryClassifier(self.llm)

        # Initialize Tavily client for web search
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            logger.warning("TAVILY_API_KEY not found, web search will be disabled")
            self.tavily_client = None
        else:
            self.tavily_client = TavilyClient(api_key=tavily_api_key)

        # Chat memory
        self.chat_memory = []
        self.max_memory_length = 10

        logger.info("Adaptive RAG Router initialized successfully")

    def clear_chat_memory(self):
        """Clear chat memory."""
        self.chat_memory = []
        logger.info("Chat memory cleared")

    def get_chat_memory(self) -> List[Dict[str, str]]:
        """Get chat memory."""
        return self.chat_memory.copy()

    def _handle_vague_document_query(self, query: str) -> Dict[str, Any]:
        """Handle vague document queries with helpful guidance."""
        response = """I'd be happy to help you with your documents! However, your question is quite general. 
        
To get the most helpful answer, please try asking more specific questions like:
• "What does the document say about [specific topic]?"
• "Summarize the main points from my uploaded files"
• "Find information about [specific subject] in my documents"
• "What are the key findings in the uploaded documents?"

If you haven't uploaded any documents yet, please upload them first using the file upload feature above."""

        return {
            "answer": response,
            "sources": [],
            "method": "vague_document_guidance",
            "evaluation_score": 0.8,
            "iteration_count": 1,
            "question": query,
        }

    def _general_conversation(self, query: str) -> Dict[str, Any]:
        """Handle general conversation queries."""
        try:
            # Create conversation context with memory
            messages = []

            # Add recent chat memory
            for memory_item in self.chat_memory[-4:]:  # Last 4 exchanges
                if memory_item["role"] == "user":
                    messages.append(HumanMessage(content=memory_item["content"]))
                else:
                    messages.append(AIMessage(content=memory_item["content"]))

            # Add current query
            messages.append(HumanMessage(content=query))

            # Generate response
            response = self.llm.invoke(messages)

            # Update chat memory
            self.chat_memory.append({"role": "user", "content": query})
            self.chat_memory.append({"role": "assistant", "content": response.content})

            # Keep memory within limit
            if len(self.chat_memory) > self.max_memory_length:
                self.chat_memory = self.chat_memory[-self.max_memory_length :]

            return {
                "answer": response.content,
                "sources": [],
                "method": "general_conversation",
                "evaluation_score": 0.9,
                "iteration_count": 1,
                "question": query,
            }

        except Exception as e:
            logger.error(f"Error in general conversation: {str(e)}")
            return {
                "answer": "I'm here to help! Feel free to ask me questions about your uploaded documents or general topics.",
                "sources": [],
                "method": "general_conversation_fallback",
                "evaluation_score": 0.5,
                "iteration_count": 1,
                "question": query,
            }

    def _web_search(self, query: str) -> Dict[str, Any]:
        """Perform web search using Tavily API."""
        try:
            if not self.tavily_client:
                return {
                    "answer": "Web search is not available. Please check your Tavily API key configuration.",
                    "sources": [],
                    "method": "web_search_unavailable",
                    "evaluation_score": 0.0,
                    "iteration_count": 1,
                    "question": query,
                }

            # Perform web search
            search_result = self.tavily_client.search(
                query=query, search_depth="advanced", max_results=5
            )

            # Extract relevant information
            sources = []
            context_parts = []

            for result in search_result.get("results", []):
                source_info = {
                    "title": result.get("title", "Unknown"),
                    "url": result.get("url", ""),
                    "content_preview": result.get("content", "")[:200] + "...",
                    "source_type": "web_search",
                }
                sources.append(source_info)
                context_parts.append(result.get("content", ""))

            # Combine context
            context = "\n\n".join(context_parts)

            # Generate answer using LLM
            prompt = f"""Based on the following web search results, provide a comprehensive and accurate answer to the question: "{query}"

Search Results:
{context}

Answer:"""

            response = self.llm.invoke(prompt)

            return {
                "answer": response.content,
                "sources": sources,
                "method": "web_search",
                "evaluation_score": 0.85,
                "iteration_count": 1,
                "question": query,
            }

        except Exception as e:
            logger.error(f"Error in web search: {str(e)}")
            return {
                "answer": f"I encountered an error while searching the web: {str(e)}. Please try rephrasing your question or ask about your uploaded documents instead.",
                "sources": [],
                "method": "web_search_error",
                "evaluation_score": 0.0,
                "iteration_count": 1,
                "question": query,
            }

    def _vectorstore_search(self, query: str) -> Dict[str, Any]:
        """Search the vector store for relevant documents."""
        try:
            if not self.rag_app:
                return {
                    "answer": "Document search is not available. Please check your RAG application configuration.",
                    "sources": [],
                    "method": "vectorstore_unavailable",
                    "evaluation_score": 0.0,
                    "iteration_count": 1,
                    "question": query,
                }

            # Get documents from RAG app
            result = self.rag_app.query(query, top_k=5)

            if not result.get("sources"):
                return {
                    "answer": "I don't have enough information in the uploaded documents to answer this question. Please upload relevant documents or try asking a different question.",
                    "sources": [],
                    "method": "vectorstore_no_results",
                    "evaluation_score": 0.3,
                    "iteration_count": 1,
                    "question": query,
                }

            return {
                "answer": result["answer"],
                "sources": result["sources"],
                "method": "vectorstore_search",
                "evaluation_score": 0.8,
                "iteration_count": 1,
                "question": query,
            }

        except Exception as e:
            logger.error(f"Error in vectorstore search: {str(e)}")
            # Check if it's the sparse vector error
            if "Sparse vector must contain at least one value" in str(e):
                return self._general_conversation(query)

            return {
                "answer": f"I encountered an error while searching your documents: {str(e)}. Please try rephrasing your question.",
                "sources": [],
                "method": "vectorstore_error",
                "evaluation_score": 0.0,
                "iteration_count": 1,
                "question": query,
            }

    def process_query(self, query: str) -> Dict[str, Any]:
        """Process a query using adaptive routing."""
        try:
            # Classify the query
            classification = self.query_classifier.classify_query(query)
            logger.info(
                f"Query classified as: {classification.classification} (confidence: {classification.confidence})"
            )

            # Route based on classification
            if classification.classification == "GENERAL":
                return self._general_conversation(query)
            elif classification.classification == "WEBSEARCH":
                return self._web_search(query)
            elif classification.classification == "VAGUE_DOCUMENT":
                return self._handle_vague_document_query(query)
            elif classification.classification == "VECTORSTORE":
                return self._vectorstore_search(query)
            else:
                # Fallback to general conversation
                return self._general_conversation(query)

        except Exception as e:
            logger.error(f"Error in Adaptive RAG: {str(e)}")
            # Fallback to simple RAG or general conversation
            try:
                if self.rag_app:
                    return self._vectorstore_search(query)
                else:
                    return self._general_conversation(query)
            except Exception as fallback_error:
                logger.error(f"Fallback error: {str(fallback_error)}")
                return {
                    "answer": "I'm experiencing technical difficulties. Please try again later or contact support.",
                    "sources": [],
                    "method": "error_fallback",
                    "evaluation_score": 0.0,
                    "iteration_count": 1,
                    "question": query,
                }
