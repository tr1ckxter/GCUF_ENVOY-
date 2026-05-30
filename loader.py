import os
import shutil
import pdfplumber
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

def extract_pdf_with_tables(file_path):
    """Extract text AND tables from a PDF, converting tables to readable markdown."""
    docs = []
    file_name = os.path.basename(file_path)

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):

            # --- Extract tables first (before plain text, to avoid double-counting) ---
            tables = page.extract_tables()
            table_texts = []
            for table in tables:
                if not table:
                    continue
                # Convert table rows to "Key: Value" pairs — much easier for the LLM to read
                rows = []
                headers = [str(cell).strip() if cell else "" for cell in table[0]]
                for row in table[1:]:
                    row_parts = []
                    for i, cell in enumerate(row):
                        cell_val = str(cell).strip() if cell else ""
                        if cell_val:
                            header = headers[i] if i < len(headers) else f"Col{i}"
                            row_parts.append(f"{header}: {cell_val}")
                    if row_parts:
                        rows.append(" | ".join(row_parts))
                if rows:
                    table_text = "[TABLE]\n" + "\n".join(rows) + "\n[/TABLE]"
                    table_texts.append(table_text)

            # --- Extract plain text ---
            plain_text = page.extract_text() or ""

            # Combine: tables go first (higher signal for fee questions)
            full_content = ""
            if table_texts:
                full_content += "\n\n".join(table_texts) + "\n\n"
            if plain_text:
                full_content += plain_text

            if full_content.strip():
                docs.append(Document(
                    page_content=full_content.strip(),
                    metadata={"source": file_path, "page": page_num + 1}
                ))

    return docs


def build_intelligence_layer():
    print("🚀 Starting Ingestion Mode...")

    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    persist_directory = "./db"
    data_path = "./data"

    if not os.path.exists(data_path):
        print(f"❌ Error: Folder '{data_path}' not found!")
        return

    files = [f for f in os.listdir(data_path) if f.endswith('.pdf')]
    if not files:
        print(f"❌ No PDFs found in '{data_path}'!")
        return

    if os.path.exists(persist_directory):
        print("🧹 Cleaning old database...")
        shutil.rmtree(persist_directory)

    # Larger chunks preserve table context; more overlap catches split rows
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        # Never split mid-table
        separators=["\n[/TABLE]", "\n\n", "\n", " ", ""]
    )

    vector_db = None

    for i, file_name in enumerate(files):
        print(f"📄 Processing ({i+1}/{len(files)}): {file_name}")

        docs = extract_pdf_with_tables(os.path.join(data_path, file_name))
        chunks = text_splitter.split_documents(docs)

        print(f"   → {len(docs)} pages, {len(chunks)} chunks")

        BATCH_SIZE = 500
        if vector_db is None:
            vector_db = Chroma.from_documents(
                documents=chunks[:BATCH_SIZE],
                embedding=embeddings,
                persist_directory=persist_directory
            )
            chunks = chunks[BATCH_SIZE:]

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            vector_db.add_documents(batch)
            print(f"   Batch {i//BATCH_SIZE + 1} done ({len(batch)} chunks)")

        print(f"✅ Done: {file_name}")

    print("\n🔥 SUCCESS! Database './db' is ready.")


if __name__ == "__main__":
    build_intelligence_layer()