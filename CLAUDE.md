# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an enhanced Python-based OCR (Optical Character Recognition) utility that extracts text from PDF documents using a flexible multi-OCR approach with modern frontend-backend separation architecture:

### OCR Service Architecture
The application supports multiple OCR services with a plugin-like architecture:

1. **阿里云DashScope OCR** - `qwen-vl-ocr-latest` model for high-precision text extraction
2. **Mistral OCR** - `pixtral-12b-2409` multimodal model with multilingual support
3. **Custom OpenAI-format OCR** - Support for any OpenAI-compatible vision API (GPT-4V, Claude 3, etc.)

### Processing Pipeline
1. **OCR Service Selection** - Interactive or GUI-based selection of OCR provider
2. **Text Extraction** - Using the selected OCR service for initial text recognition
3. **Intelligent Correction** - Google Gemini 2.5 Flash for text correction and formatting
4. **Markdown Output** - Structured document formatting with automatic layout recognition

The application features multiple interface modes:
- **Web Interface** (FastAPI + HTML/CSS/JS) - Modern responsive web UI with drag-drop file upload
- **Command Line Interface** - Interactive text-based interface for batch processing
- **Traditional GUI** (Tkinter) - Desktop application with native OS integration

All interfaces support file selection, OCR service selection, page range configuration, terminology correction, and comprehensive error handling with real-time progress tracking.

## Development Commands

### Package Management
- **Install dependencies**: `uv sync` (uses uv package manager)
- **Add dependency**: `uv add <package-name>`
- **Update dependencies**: `uv sync --upgrade`

### Running the Application
- **智能启动器**: `python launcher.py` (自动选择最佳运行模式)
- **命令行模式**: `python launcher.py cli` 或 `python main.py`
- **Web界面模式**: `python launcher.py web` 或 `python backend.py` (推荐)
- **传统GUI模式**: `python launcher.py gui` 或 `python gui_main.py`
- **Activate virtual environment**: `source .venv/bin/activate` (if needed)

### Python Version
- **Required version**: Python >=3.13 (specified in `.python-version`)

## Architecture

### Core Components

1. **main.py** - Core OCR processing engine with interactive CLI features:
   - Interactive file selection from `input/` directory
   - Interactive page range selection with PDF page count detection
   - Multi-API processing with pluggable OCR services + Gemini correction
   - Automatic text merging and comprehensive output management
   - Progress tracking and error handling

2. **backend.py** - FastAPI web server providing RESTful API:
   - File upload and management endpoints
   - Asynchronous OCR processing with progress tracking
   - WebSocket-like progress updates via polling
   - Result download and management
   - CORS-enabled for frontend integration

3. **web/** - Modern web frontend:
   - **index.html** - Responsive single-page application
   - **style.css** - Modern CSS with dark/light theme support
   - **app.js** - JavaScript client with real-time progress updates

4. **gui_main.py** - Traditional Tkinter desktop GUI:
   - Native OS integration and file dialogs
   - Modern styling with custom themes
   - Multi-threaded processing to prevent UI freezing

5. **launcher.py** - Intelligent application launcher:
   - Automatic mode detection and selection
   - Command-line argument support
   - Dependency checking and error handling

6. **Configuration** - Environment-based configuration via `.env` with multiple OCR service support:
   - `GEMINI_API_KEY` - Google Gemini API key (required for text correction)
   - `GEMINI_BASE_URL` - Gemini API service URL (required)
   - `DASHSCOPE_API_KEY` - Alibaba DashScope API key (optional)
   - `MISTRAL_API_KEY` - Mistral API key (optional)
   - `MISTRAL_BASE_URL` - Mistral API base URL (defaults to official API)
   - `CUSTOM_OCR_API_KEY` - Custom OpenAI-format OCR service API key (optional)
   - `CUSTOM_OCR_BASE_URL` - Custom OCR service base URL (optional)
   
   Note: At least one OCR service must be configured.

7. **Enhanced Data Flow**:
   ```
   User Selection → OCR Service Selection → PDF → pdf2image → PIL Image → base64 Data URI 
   → Selected OCR API → Raw OCR Text → Gemini Correction API 
   → Corrected Text → Individual Page Files + Combined File
   ```

### Interactive Features

- **OCR Service Selection**: Choose from available OCR providers (DashScope, Mistral, Custom)
- **File Selection**: Automatically scans `input/` directory for PDF files
- **Batch Processing**: Option to process single file or all files
- **Page Range**: Interactive selection with automatic PDF page count detection
- **Terminology Support**: Optional custom terminology files for improved accuracy
- **Progress Tracking**: Real-time progress bars with per-page status updates and token consumption

### Key Dependencies

**Core Processing:**
- **pdf2image**: PDF to image conversion (requires Poppler system dependency)
- **openai**: OpenAI-compatible client for DashScope API
- **google-generativeai**: Google Gemini API client for text correction
- **pypdf**: PDF page count detection and metadata reading
- **pillow**: Image processing and format conversion
- **tqdm**: Progress tracking for batch processing
- **python-dotenv**: Environment variable management

**Web Backend:**
- **fastapi**: Modern web framework for building APIs
- **uvicorn**: ASGI server for FastAPI applications
- **python-multipart**: File upload support for FastAPI

**GUI (Optional):**
- **tkinter**: Traditional desktop GUI (built into Python)

### System Requirements

- **Poppler**: Required for PDF processing
  - macOS: `brew install poppler` 
  - Ubuntu/Debian: `sudo apt-get install poppler-utils`

### Input/Output Structure

- **Input**: `input/` directory containing PDF files (automatically scanned)
- **Output**: `ocr_output/` directory with organized text files:
  - Individual pages: `{filename}_page_{number}.txt`
  - Combined file: `{filename}_combined.txt`
- **Configuration**: `.env` file in project root with API keys only

### Error Handling

The application includes comprehensive error handling for:
- Missing environment variables (API keys)
- PDF conversion failures with helpful installation messages
- Page processing errors with graceful skipping and continuation
- API failures with fallback to original text
- Interactive input validation with retry mechanisms

### Multi-OCR API Integration

#### OCR Services (Choose one or more):

1. **DashScope OCR** (Specialized OCR):
   - Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
   - Model: `qwen-vl-ocr-latest`
   - Supports streaming responses for real-time processing
   - Configurable image resolution parameters for optimal OCR quality
   - Best for: High-precision text extraction, especially Chinese/English

2. **Mistral OCR** (Multimodal AI):
   - Base URL: `https://api.mistral.ai/v1`
   - Model: `pixtral-12b-2409`
   - Advanced multimodal understanding
   - Best for: Complex layouts, multilingual documents

3. **Custom OpenAI-format OCR** (Flexible integration):
   - Configurable base URL
   - Support for GPT-4V, Claude 3, and other vision models
   - OpenAI-compatible API format
   - Best for: Custom deployments, specific model requirements

#### Text Correction Service (Required):

**Google Gemini** (Text correction and enhancement):
   - Model: `gemini-2.5-flash`
   - Intelligent error correction for OCR artifacts
   - Context-aware text improvement while preserving meaning
   - Markdown formatting with structure recognition
   - Fallback to original text on API failures