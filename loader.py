import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

def build_intelligence_layer():
    print("🚀 Starting Ingestion Mode...")
    
    # 1. Setup the Librarian (Embedding Model)
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    
    # 2. Set the destination
    persist_directory = "./db"
    
    # 3. Find your PDFs
    data_path = "./data"
    
    if not os.path.exists(data_path):
        print(f"❌ Error: Folder {data_path} not found! Create it and put your PDFs inside.")
        return

    files = [f for f in os.listdir(data_path) if f.endswith('.pdf')]
    
    if not files:
        print(f"❌ No PDF files found in {data_path}!")
        return
    
    if os.path.exists(persist_directory):
        import shutil
        print("🧹 Cleaning old database for a fresh start...")
        shutil.rmtree(persist_directory)

    vector_db = None

    for i, file_name in enumerate(files):
        print(f"📄 Processing ({i+1}/{len(files)}): {file_name}")
        
        # Load the PDF
        loader = PyPDFLoader(os.path.join(data_path, file_name))
        docs = loader.load()
        
        # Split into small chunks (500 characters each)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = text_splitter.split_documents(docs)
        
        # Add to database
        if vector_db is None:
            vector_db = Chroma.from_documents(
                documents=chunks, 
                embedding=embeddings, 
                persist_directory=persist_directory
            )
        else:
            vector_db.add_documents(chunks)
        
        print(f"✅ Added {len(chunks)} chunks from {file_name}")

    print("\n🔥 SUCCESS! Database './db' is now full of knowledge.")

if __name__ == "__main__":
    build_intelligence_layer()