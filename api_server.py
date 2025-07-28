import os
import tempfile
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from hybrid_rag_app import HybridRAGApp
from smart_rag_router import AdaptiveRAGRouter

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global variables
rag_app = None
adaptive_router = None


def get_rag_app():
    """Initialize and return RAG application instance."""
    global rag_app
    if rag_app is None:
        try:
            rag_app = HybridRAGApp()
            logger.info("RAG application initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG application: {str(e)}")
            raise e
    return rag_app


def get_adaptive_router():
    """Initialize and return Adaptive RAG Router instance."""
    global adaptive_router
    if adaptive_router is None:
        try:
            rag_app = get_rag_app()
            adaptive_router = AdaptiveRAGRouter(rag_app)
            logger.info("Adaptive RAG Router initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Adaptive RAG Router: {str(e)}")
            raise e
    return adaptive_router


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    try:
        get_rag_app()
        return jsonify(
            {"status": "healthy", "message": "Adaptive RAG API is running"}
        ), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route("/stats", methods=["GET"])
def get_stats():
    """Get Pinecone index statistics."""
    try:
        rag_app = get_rag_app()
        stats = rag_app.get_index_stats()

        if stats and not isinstance(stats, dict):
            stats = {"error": "Invalid stats format"}
        elif not stats:
            stats = {"total_vector_count": 0, "dimension": 384, "index_fullness": 0}

        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify(
            {
                "total_vector_count": 0,
                "dimension": 384,
                "index_fullness": 0,
                "error": str(e),
            }
        ), 200


@app.route("/upload", methods=["POST"])
def upload_files():
    """Upload and process documents."""
    try:
        if "files" not in request.files:
            return jsonify({"success": False, "error": "No files provided"}), 400

        files = request.files.getlist("files")
        if not files or all(file.filename == "" for file in files):
            return jsonify({"success": False, "error": "No files selected"}), 400

        rag_app = get_rag_app()
        uploaded_files = []
        processing_stats = {
            "total_files": len(files),
            "successful_files": 0,
            "failed_files": 0,
        }

        for file in files:
            if file.filename:
                try:
                    # Create temporary file
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=os.path.splitext(file.filename)[1]
                    ) as temp_file:
                        file.save(temp_file.name)
                        temp_file_path = temp_file.name

                    # Process the file
                    stats = rag_app.add_documents([temp_file_path])

                    # Clean up temporary file
                    os.unlink(temp_file_path)

                    if stats["successful_files"] > 0:
                        uploaded_files.append(file.filename)
                        processing_stats["successful_files"] += 1
                    else:
                        processing_stats["failed_files"] += 1

                except Exception as e:
                    logger.error(f"Error processing {file.filename}: {str(e)}")
                    processing_stats["failed_files"] += 1
                    continue

        if processing_stats["successful_files"] > 0:
            return jsonify(
                {
                    "success": True,
                    "message": f"Successfully uploaded {processing_stats['successful_files']} files",
                    "uploaded_files": uploaded_files,
                    "stats": processing_stats,
                }
            ), 200
        else:
            return jsonify(
                {
                    "success": False,
                    "error": "Failed to process any files",
                    "stats": processing_stats,
                }
            ), 400

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/query", methods=["POST"])
def query():
    """Process user queries with adaptive routing."""
    try:
        data = request.get_json()
        if not data or "question" not in data:
            return jsonify({"error": "No question provided"}), 400

        question = data["question"].strip()
        if not question:
            return jsonify({"error": "Empty question"}), 400

        adaptive_router = get_adaptive_router()
        result = adaptive_router.process_query(question)

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@app.route("/clear", methods=["POST"])
def clear_index():
    """Clear the Pinecone index."""
    try:
        rag_app = get_rag_app()
        rag_app.clear_index()
        return jsonify({"success": True, "message": "Index cleared successfully"}), 200
    except Exception as e:
        logger.error(f"Clear index error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/formats", methods=["GET"])
def get_formats():
    """Get supported file formats."""
    try:
        rag_app = get_rag_app()
        formats = rag_app.get_supported_formats()
        return jsonify({"formats": formats}), 200
    except Exception as e:
        logger.error(f"Get formats error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/chat/memory", methods=["GET"])
def get_chat_memory():
    """Get chat memory."""
    try:
        adaptive_router = get_adaptive_router()
        memory = adaptive_router.get_chat_memory()
        return jsonify({"memory": memory}), 200
    except Exception as e:
        logger.error(f"Get memory error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/chat/memory", methods=["DELETE"])
def clear_chat_memory():
    """Clear chat memory."""
    try:
        adaptive_router = get_adaptive_router()
        adaptive_router.clear_chat_memory()
        return jsonify({"success": True, "message": "Chat memory cleared"}), 200
    except Exception as e:
        logger.error(f"Clear memory error: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Development server - use production_server.py for production
    port = int(os.getenv('PORT', 4001))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    print(f"🚀 Starting Adaptive RAG API Server...")
    print(f"📍 Port: {port}")
    print(f"🔧 Debug: {debug}")
    print(f"🌍 Environment: {os.getenv('FLASK_ENV', 'development')}")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
