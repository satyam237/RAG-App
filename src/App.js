import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Upload, 
  Send, 
  FileText, 
  MessageSquare, 
  Loader2, 
  AlertCircle,
  Bot,
  User,
  Trash2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Globe,
  Database
} from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:4001';

// Helper function to format file size
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

// Component for formatted AI response
const FormattedResponse = ({ content }) => {
  const formatResponse = (text) => {
    if (!text) return '';
    
    let formatted = text
      .replace(/(\d+\.\s)/g, '\n$1')
      .replace(/(\*\*Domain:\*\*)/g, '\n\n$1')
      .replace(/(\*\*Problem Statement:\*\*)/g, '\n\n$1')
      .replace(/(\*\*[^*]+\*\*)/g, '\n$1')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
    
    return formatted;
  };

  const formattedText = formatResponse(content);
  const lines = formattedText.split('\n');

  return (
    <div className="space-y-2">
      {lines.map((line, index) => {
        if (line.match(/^\d+\.\s/)) {
          const number = line.match(/^\d+/)[0];
          const content = line.replace(/^\d+\.\s/, '');
          
          return (
            <div key={index} className="flex items-start space-x-2">
              <span className="text-primary-600 font-medium min-w-[20px]">
                {number}.
              </span>
              <div className="flex-1">
                {content.split('**').map((part, partIndex) => {
                  if (partIndex % 2 === 1) {
                    return (
                      <span key={partIndex} className="font-semibold text-gray-800">
                        {part}
                      </span>
                    );
                  } else {
                    return (
                      <span key={partIndex} className="text-gray-700">
                        {part}
                      </span>
                    );
                  }
                })}
              </div>
            </div>
          );
        }
        
        if (line.match(/^\*\*[^*]+\*\*:/)) {
          return (
            <div key={index} className="font-semibold text-gray-800 mt-3 first:mt-0">
              {line.replace(/\*\*/g, '')}
            </div>
          );
        }
        
        if (line.match(/^\*\*[^*]+\*\*$/)) {
          return (
            <div key={index} className="font-semibold text-gray-800">
              {line.replace(/\*\*/g, '')}
            </div>
          );
        }
        
        if (line.trim()) {
          return (
            <div key={index} className="text-gray-700">
              {line.split('**').map((part, partIndex) => {
                if (partIndex % 2 === 1) {
                  return (
                    <span key={partIndex} className="font-semibold text-gray-800">
                      {part}
                    </span>
                  );
                } else {
                  return (
                    <span key={partIndex} className="text-gray-700">
                      {part}
                    </span>
                  );
                }
              })}
            </div>
          );
        }
        
        return null;
      })}
    </div>
  );
};

// Component for sources dropdown
const SourcesDropdown = ({ sources, method }) => {
  const [isOpen, setIsOpen] = useState(false);

  const getMethodIcon = () => {
    switch (method) {
      case 'web_search':
        return <Globe className="w-4 h-4" />;
      case 'vectorstore_search':
        return <Database className="w-4 h-4" />;
      default:
        return <FileText className="w-4 h-4" />;
    }
  };

  const getMethodText = () => {
    switch (method) {
      case 'web_search':
        return 'Web Search';
      case 'vectorstore_search':
        return 'Document Search';
      default:
        return 'Sources';
    }
  };

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 text-xs text-gray-500 hover:text-gray-700 transition-colors"
      >
        {getMethodIcon()}
        <span>{getMethodText()} ({sources.length})</span>
        {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="mt-2 space-y-2"
        >
          {sources.map((source, index) => (
            <div key={index} className="bg-gray-50 rounded-lg p-3 text-xs">
              <div className="font-medium text-gray-800 mb-1">
                {source.title || source.file_name || `Source ${index + 1}`}
              </div>
              <div className="text-gray-600">
                {source.content_preview || source.url || 'No preview available'}
              </div>
              {source.url && (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-600 hover:text-primary-700 text-xs mt-1 inline-block"
                >
                  View source →
                </a>
              )}
            </div>
          ))}
        </motion.div>
      )}
    </div>
  );
};

function App() {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);
  const [question, setQuestion] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadStatus, setUploadStatus] = useState('');
  const [stats, setStats] = useState({ total_vector_count: 0 });
  const [error, setError] = useState('');
  const [uploadedDocuments, setUploadedDocuments] = useState([]);
  const fileInputRef = useRef(null);

  const initializeApp = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/health`);
      if (response.data.status === 'healthy') {
        const statsResponse = await axios.get(`${API_BASE_URL}/stats`);
        setStats(statsResponse.data);
        setIsInitialized(true);
        setError('');
      }
    } catch (err) {
      setError('Failed to initialize the application. Please check your API keys.');
      console.error('Initialization error:', err);
    }
  };

  useEffect(() => {
    initializeApp();
  }, []);

  const handleFileUpload = async () => {
    if (selectedFiles.length === 0) {
      setUploadStatus('Please select files to upload.');
      return;
    }

    setUploadStatus('Uploading files...');
    const formData = new FormData();
    
    selectedFiles.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setUploadStatus(`Successfully uploaded ${response.data.stats.successful_files} files!`);
        
        // Add uploaded documents to the list
        const newDocuments = selectedFiles.map(file => ({
          name: file.name,
          size: file.size,
          type: file.type,
          uploadedAt: new Date().toLocaleString()
        }));
        setUploadedDocuments(prev => [...prev, ...newDocuments]);
        
        setSelectedFiles([]);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        
        // Update stats
        const statsResponse = await axios.get(`${API_BASE_URL}/stats`);
        setStats(statsResponse.data);
      } else {
        setUploadStatus(`Upload failed: ${response.data.error}`);
      }
    } catch (err) {
      setUploadStatus(`Upload failed: ${err.response?.data?.error || err.message}`);
    }
  };

  const handleFileSelect = (event) => {
    setSelectedFiles(Array.from(event.target.files));
  };

  const clearIndex = async () => {
    try {
      await axios.post(`${API_BASE_URL}/clear`);
      setStats({ total_vector_count: 0 });
      setChatHistory([]);
      setUploadedDocuments([]);
      setUploadStatus('Index cleared successfully!');
    } catch (err) {
      setUploadStatus(`Failed to clear index: ${err.message}`);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim() || isQuerying) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: question,
      timestamp: new Date().toLocaleTimeString(),
    };

    setChatHistory(prev => [...prev, userMessage]);
    setQuestion('');
    setIsQuerying(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/query`, {
        question: question.trim(),
      });

      const aiMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: response.data.answer,
        sources: response.data.sources || [],
        method: response.data.method || 'unknown',
        timestamp: new Date().toLocaleTimeString(),
      };

      setChatHistory(prev => [...prev, aiMessage]);
    } catch (err) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: `Error: ${err.response?.data?.error || err.message}`,
        sources: [],
        method: 'error',
        timestamp: new Date().toLocaleTimeString(),
      };

      setChatHistory(prev => [...prev, errorMessage]);
    } finally {
      setIsQuerying(false);
    }
  };

  if (!isInitialized) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary-600" />
          <p className="text-gray-600">{error || 'Initializing application...'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-6">
          <div className="flex justify-between items-center py-3">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <MessageSquare className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Adaptive RAG</h1>
                <p className="text-sm text-gray-500">
                  {uploadedDocuments.length > 0 ? `${uploadedDocuments.length} documents uploaded` : `${stats.total_vector_count} documents indexed`}
                </p>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <button
                onClick={clearIndex}
                className="btn-secondary text-xs"
                title="Clear all documents"
              >
                <Trash2 className="w-4 h-4" />
              </button>
              <button
                onClick={initializeApp}
                className="btn-secondary text-xs"
                title="Refresh"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-6 py-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 xl:grid-cols-4 gap-4 lg:gap-6">
          {/* Chat Section - Mobile First, then Sidebar */}
          <div className="lg:col-span-2 xl:col-span-3 order-1 lg:order-2">
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="card h-[calc(100vh-120px)] min-h-[500px] flex flex-col"
            >
              {/* Chat Header */}
              <div className="p-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-gray-900">Chat</h3>
                  

                </div>
              </div>

              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {chatHistory.length === 0 ? (
                  <div className="text-center text-gray-500 py-8">
                    <Bot className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Upload documents and start asking questions!</p>
                  </div>
                ) : (
                  <AnimatePresence>
                    {chatHistory.map((message) => (
                      <motion.div
                        key={message.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div className={`max-w-[80%] ${message.type === 'user' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-900'} rounded-lg px-4 py-3`}>
                          <div className="flex items-start">
                            {message.type === 'user' ? (
                              <User className="w-6 h-6 mr-3 flex-shrink-0" />
                            ) : (
                              <Bot className="w-6 h-6 mr-3 flex-shrink-0 text-primary-600" />
                            )}
                            <div className="flex-1">
                              {message.type === 'ai' ? (
                                <FormattedResponse content={message.content} />
                              ) : (
                                <p className="text-sm">{message.content}</p>
                              )}
                              
                              {message.sources && message.sources.length > 0 && (
                                <SourcesDropdown sources={message.sources} method={message.method} />
                              )}
                              
                              <p className="text-xs opacity-70 mt-2">{message.timestamp}</p>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                )}
                
                {isQuerying && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-start"
                  >
                    <div className="bg-gray-100 rounded-lg px-4 py-3">
                      <div className="flex items-center space-x-2">
                        <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
                        <span className="text-sm text-gray-600">Thinking...</span>
                      </div>
                    </div>
                  </motion.div>
                )}
              </div>

              {/* Input Form */}
              <div className="p-4 border-t border-gray-200">
                <form onSubmit={handleSubmit} className="flex space-x-3">
                  <input
                    type="text"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Ask a question..."
                    className="input-field flex-1"
                    disabled={isQuerying}
                  />
                  <button
                    type="submit"
                    disabled={isQuerying || !question.trim()}
                    className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            </motion.div>
          </div>

          {/* Left Sidebar - Upload & Features */}
          <div className="lg:col-span-1 xl:col-span-1 space-y-6 order-2 lg:order-1">
            {/* Upload Section */}
            <motion.div 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="card"
            >
              <div className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Documents</h3>
                
                <div className="space-y-4">
                  <div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      onChange={handleFileSelect}
                      className="hidden"
                      accept=".pdf,.doc,.docx,.txt,.pptx,.csv,.png,.jpg,.jpeg"
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="btn-secondary w-full flex items-center justify-center space-x-2"
                    >
                      <Upload className="w-4 h-4" />
                      <span>Select Files</span>
                    </button>
                  </div>
                  
                  {selectedFiles.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm text-gray-600">
                        Selected {selectedFiles.length} file(s):
                      </p>
                      <div className="max-h-32 overflow-y-auto space-y-1">
                        {selectedFiles.map((file, index) => (
                          <div key={index} className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                            {file.name}
                          </div>
                        ))}
                      </div>
                      <button
                        onClick={handleFileUpload}
                        className="btn-primary w-full flex items-center justify-center space-x-2"
                      >
                        <Upload className="w-4 h-4" />
                        <span>Upload Files</span>
                      </button>
                    </div>
                  )}
                  
                  {uploadStatus && (
                    <div className={`text-sm p-3 rounded-lg ${
                      uploadStatus.includes('Successfully') || uploadStatus.includes('cleared')
                        ? 'bg-green-50 text-green-700'
                        : uploadStatus.includes('Error') || uploadStatus.includes('Failed')
                        ? 'bg-red-50 text-red-700'
                        : 'bg-blue-50 text-blue-700'
                    }`}>
                      {uploadStatus}
                    </div>
                  )}
                  
                  {/* Uploaded Documents Display */}
                  {uploadedDocuments.length > 0 && (
                    <div className="mt-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">
                        Documents in Chat ({uploadedDocuments.length})
                      </h4>
                      <div className="max-h-32 overflow-y-auto space-y-2">
                        {uploadedDocuments.map((doc, index) => (
                          <div key={index} className="flex items-center justify-between bg-gray-50 p-2 rounded-lg">
                            <div className="flex items-center space-x-2 flex-1 min-w-0">
                              <FileText className="w-4 h-4 text-gray-500 flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium text-gray-800 truncate" title={doc.name}>
                                  {doc.name}
                                </p>
                                <p className="text-xs text-gray-500">
                                  {formatFileSize(doc.size)} • {doc.uploadedAt}
                                </p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>

            {/* Features Showcase */}
            <motion.div 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
              className="card"
            >
              <div className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Key Features</h3>
                
                <div className="space-y-3 max-h-[400px] overflow-y-auto">
                  {uploadedDocuments.length > 0 && (
                    <div className="bg-gradient-to-r from-emerald-50 to-emerald-100 p-3 rounded-lg">
                      <div className="flex items-center space-x-2 mb-2">
                        <FileText className="w-4 h-4 text-emerald-600" />
                        <span className="font-medium text-emerald-800">Active Documents</span>
                      </div>
                      <p className="text-xs text-emerald-700">
                        {uploadedDocuments.length} document{uploadedDocuments.length !== 1 ? 's' : ''} ready for chat
                      </p>
                    </div>
                  )}
                  <div className="bg-gradient-to-r from-blue-50 to-blue-100 p-3 rounded-lg">
                    <div className="flex items-center space-x-2 mb-2">
                      <Database className="w-4 h-4 text-blue-600" />
                      <span className="font-medium text-blue-800">Hybrid Search</span>
                    </div>
                    <p className="text-xs text-blue-700">Combines dense vector search with sparse keyword search for high accuracy</p>
                  </div>
                  
                  <div className="bg-gradient-to-r from-green-50 to-green-100 p-3 rounded-lg">
                    <div className="flex items-center space-x-2 mb-2">
                      <FileText className="w-4 h-4 text-green-600" />
                      <span className="font-medium text-green-800">Multi-Document Support</span>
                    </div>
                    <p className="text-xs text-green-700">Upload and chat with multiple documents simultaneously</p>
                  </div>
                  
                  <div className="bg-gradient-to-r from-purple-50 to-purple-100 p-3 rounded-lg">
                    <div className="flex items-center space-x-2 mb-2">
                      <Globe className="w-4 h-4 text-purple-600" />
                      <span className="font-medium text-purple-800">Web Search</span>
                    </div>
                    <p className="text-xs text-purple-700">Automatic web search for current information and real-time data</p>
                  </div>
                  
                  <div className="bg-gradient-to-r from-orange-50 to-orange-100 p-3 rounded-lg">
                    <div className="flex items-center space-x-2 mb-2">
                      <Bot className="w-4 h-4 text-orange-600" />
                      <span className="font-medium text-orange-800">Smart Routing</span>
                    </div>
                    <p className="text-xs text-orange-700">AI-powered query classification for optimal response selection</p>
                  </div>
                  
                  <div className="bg-gradient-to-r from-red-50 to-red-100 p-3 rounded-lg">
                    <div className="flex items-center space-x-2 mb-2">
                      <Upload className="w-4 h-4 text-red-600" />
                      <span className="font-medium text-red-800">Multiple Formats</span>
                    </div>
                    <p className="text-xs text-red-700">Support for PDF, DOC, DOCX, PPTX, TXT, CSV, and images</p>
                  </div>
                  
                  <div className="bg-gradient-to-r from-indigo-50 to-indigo-100 p-3 rounded-lg">
                    <div className="flex items-center space-x-2 mb-2">
                      <RefreshCw className="w-4 h-4 text-indigo-600" />
                      <span className="font-medium text-indigo-800">Real-time Processing</span>
                    </div>
                    <p className="text-xs text-indigo-700">Instant document processing and intelligent text extraction</p>
                  </div>
                </div>
                
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Technologies Used</h4>
                  <div className="flex flex-wrap gap-1">
                    <span className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">React</span>
                    <span className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">Flask</span>
                    <span className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">LangChain</span>
                    <span className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">Pinecone</span>
                    <span className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">OpenAI</span>
                    <span className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">Tavily</span>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App; 