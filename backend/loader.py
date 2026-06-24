import os
import shutil
import logging
import pdfplumber
from typing import List, Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
PERSIST_DIRECTORY = "./db"
DATA_PATH = "./data"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
BATCH_SIZE = 500


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Initialize HuggingFace sentence-transformers embedding model.
    Uses all-MiniLM-L6-v2 — lightweight 22M parameter model producing
    384-dimensional vectors. Runs locally with no API cost.
    """
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )


def extract_pdf_with_tables(file_path: str) -> List[Document]:
    """
    Extract structured content from a PDF file using pdfplumber.
    Tables are converted to key-value pairs for better LLM readability.
    Returns one Document per non-empty page with source and page metadata.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")

    docs: List[Document] = []
    file_name = os.path.basename(file_path)
    pages_processed = 0
    pages_skipped = 0

    try:
        with pdfplumber.open(file_path) as pdf:
            logger.info(f"  Opened '{file_name}' — {len(pdf.pages)} pages")

            for page_num, page in enumerate(pdf.pages):
                try:
                    table_texts = []

                    for table in page.extract_tables():
                        if not table or len(table) < 2:
                            continue

                        headers = [
                            str(cell).strip() if cell else f"Col{i}"
                            for i, cell in enumerate(table[0])
                        ]

                        rows = []
                        for row in table[1:]:
                            row_parts = []
                            for i, cell in enumerate(row):
                                cell_val = str(cell).strip() if cell else ""
                                # Skip empty or null cells
                                if cell_val and cell_val.lower() != "none":
                                    header = headers[i] if i < len(headers) else f"Col{i}"
                                    row_parts.append(f"{header}: {cell_val}")
                            if row_parts:
                                rows.append(" | ".join(row_parts))

                        if rows:
                            table_texts.append(
                                "[TABLE]\n" + "\n".join(rows) + "\n[/TABLE]"
                            )

                    plain_text = page.extract_text() or ""

                    full_content = ""
                    if table_texts:
                        full_content += "=== TABLE DATA ===\n"
                        full_content += "\n\n".join(table_texts)
                        full_content += "\n\n=== END TABLE DATA ===\n\n"
                    if plain_text:
                        full_content += "=== TEXT CONTENT ===\n"
                        full_content += plain_text

                    if full_content.strip():
                        docs.append(Document(
                            page_content=full_content.strip(),
                            metadata={
                                "source": file_path,
                                "page": page_num + 1,
                                "file_name": file_name,
                            }
                        ))
                        pages_processed += 1
                    else:
                        pages_skipped += 1

                except Exception as page_error:
                    logger.warning(f"  Skipping page {page_num + 1}: {page_error}")
                    pages_skipped += 1
                    continue

    except Exception as e:
        logger.error(f"Failed to process '{file_name}': {e}")
        return docs

    logger.info(f"  Extracted {pages_processed} pages ({pages_skipped} skipped)")
    return docs


def build_intelligence_layer(
    data_path: str = DATA_PATH,
    persist_directory: str = PERSIST_DIRECTORY
) -> Optional[Chroma]:
    """
    Main document ingestion pipeline for GCUF Envoy.
    Discovers PDFs, extracts content, chunks, embeds, and stores in ChromaDB.

    Args:
        data_path: Directory containing source PDF files.
        persist_directory: ChromaDB storage location.

    Returns:
        Populated Chroma vector database instance, or None if ingestion fails.

    Example:
        >>> db = build_intelligence_layer()
        >>> results = db.similarity_search("BS Software Engineering fee")
    """
    logger.info("=" * 50)
    logger.info("GCUF Envoy — Document Ingestion Pipeline")
    logger.info("=" * 50)

    if not os.path.exists(data_path):
        logger.error(f"Data directory not found: '{data_path}'")
        return None

    files = [f for f in os.listdir(data_path) if f.endswith(".pdf")]
    if not files:
        logger.error(f"No PDF files found in '{data_path}'")
        return None

    logger.info(f"Found {len(files)} PDF file(s): {', '.join(files)}")

    if os.path.exists(persist_directory):
        logger.info(f"Removing existing database at '{persist_directory}'")
        shutil.rmtree(persist_directory)

    embeddings = get_embeddings()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # Never split mid-table
        separators=["\n[/TABLE]", "\n\n", "\n", " ", ""]
    )

    vector_db: Optional[Chroma] = None
    total_chunks = 0

    for i, file_name in enumerate(files):
        logger.info(f"Processing ({i+1}/{len(files)}): {file_name}")

        docs = extract_pdf_with_tables(os.path.join(data_path, file_name))

        if not docs:
            logger.warning(f"No content extracted from '{file_name}' — skipping.")
            continue

        chunks = text_splitter.split_documents(docs)
        total_chunks += len(chunks)
        logger.info(f"  → {len(docs)} pages → {len(chunks)} chunks")

        try:
            if vector_db is None:
                logger.info("  Initializing ChromaDB...")
                vector_db = Chroma.from_documents(
                    documents=chunks[:BATCH_SIZE],
                    embedding=embeddings,
                    persist_directory=persist_directory
                )
                chunks = chunks[BATCH_SIZE:]

            for j in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[j:j + BATCH_SIZE]
                vector_db.add_documents(batch)
                logger.info(f"  Batch {j//BATCH_SIZE + 1} done ({len(batch)} chunks)")

        except Exception as e:
            logger.error(f"Failed to store chunks from '{file_name}': {e}")
            continue

        logger.info(f"✅ Done: {file_name}")

    if vector_db is None:
        logger.error("No documents were ingested. Database was not created.")
        return None

    logger.info("=" * 50)
    logger.info(f"✅ Ingestion complete!")
    logger.info(f"   Files processed : {len(files)}")
    logger.info(f"   Total chunks    : {total_chunks}")
    logger.info(f"   Database saved  : {persist_directory}")
    logger.info("=" * 50)

    return vector_db


if __name__ == "__main__":
    build_intelligence_layer()