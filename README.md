# GCUF Envoy

An AI-powered university assistant for Government College University Faisalabad (GCUF).  
It allows students to ask natural language questions about admissions, fee structures, academic programs, and university policies using a Retrieval-Augmented Generation (RAG) system.

Deployed on Microsoft Azure with a Flutter Android client.

---

## What It Does

Students can ask questions like:

- What is the fee for BS Software Engineering?
- What are the admission requirements?
- What programs are offered at GCUF?

The system retrieves relevant university documents and generates accurate, grounded answers using an LLM.

---

## System Architecture

User Query
↓
FastAPI Backend
↓
Cache Check (MD5 Hash)
↓
Query Classification (fee / admission / general)
↓
ChromaDB Retrieval (MMR Search)
↓
Context Formatting
↓
Groq LLM (Llama 3.3 70B)
↓
Cached Response
↓
Flutter Client

---

## 📄 Ingestion Pipeline

PDFs → Text Extraction → Chunking → Embeddings → ChromaDB

- PDF content is extracted using **PDFplumber**
- Text is split into meaningful chunks using **RecursiveTextSplitter**
- Embeddings are generated using **MiniLM (384-dim vectors)**
- Stored in **ChromaDB** with metadata for retrieval

---

## Tech Stack

| Component      | Technology        |
| -------------- | ----------------- |
| Frontend       | Flutter (Android) |
| Backend        | FastAPI           |
| PDF Processing | pdfplumber        |
| Embeddings     | MiniLM-L6-v2      |
| Vector DB      | ChromaDB          |
| LLM            | Groq API          |
| Deployment     | Microsoft Azure   |

---

## Key Features

- Retrieval-Augmented Generation (RAG) pipeline
- Query classification for better retrieval accuracy
- Metadata-based document filtering
- Max Marginal Relevance for diverse results
- Response caching using MD5 hashing
- FastAPI backend with Flutter integration

---

## Technical Highlights

- Used **MMR retrieval** instead of plain similarity search to improve diversity of context chunks
- Implemented **query classification** to route questions to relevant document sources
- Built **caching layer** to reduce repeated LLM calls and improve response speed
- Designed ingestion pipeline with structured chunking and metadata tagging
- Optimized embeddings using **MiniLM** for efficient CPU-based inference

---

## Known Limitations

- Cache resets on server restart (in-memory cache)
- Query classification uses LLM calls (can be optimized to deterministic rules)
- Full ChromaDB rebuild required when data changes
- Retrieval currently scans all chunks before filtering
- Basic metadata structure (can be improved in future phases)

---

## Roadmap

- [x] Phase 1 — Core RAG system (completed, deployed on Azure)
- [ ] Phase 2 — Advanced metadata tagging & improved filtering
- [ ] Phase 3 — Replace LLM-based classifier with lightweight router
- [ ] Phase 4 — Evaluation & benchmarking system for RAG performance

---

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env

# Build vector database
python loader.py

# Run backend
python main.py
```
