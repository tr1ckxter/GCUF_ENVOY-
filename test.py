from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# Connect to the brain you just built
embeddings = OllamaEmbeddings(model="mxbai-embed-large")
db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# Ask something only the PDFs would know
query = "What is the specific admission criteria for BS Software Engineering?"
docs = db.similarity_search(query, k=2)

print("\n--- DATA RETRIEVAL TEST ---")
for i, doc in enumerate(docs):
    print(f"\nSection {i+1} found in PDF:")
    print(doc.page_content[:300] + "...")