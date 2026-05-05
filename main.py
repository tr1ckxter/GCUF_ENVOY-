import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_community.vectorstores import Chroma
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. Load the Database ---
print("--- 🧠 Loading Database ---")
embeddings = OllamaEmbeddings(model="nomic-embed-text") 
vector_db = Chroma(persist_directory="./db", embedding_function=embeddings)

# --- 2. Setup the Brain ---
# Verify this name matches 'ollama list'
llm = OllamaLLM(model="gemma3:4b") 

@app.post("/query")
async def ask_question(request: Request):
    try:
        data = await request.json()
        query = data.get("query")
        
        print(f"📱 Phone sent query: {query}")
        
        # --- 3. RETRIEVAL CHECK ---
        docs = vector_db.max_marginal_relevance_search(query, k=6, fetch_k=20)
        
        print(f"📄 Found {len(docs)} matching snippets.")
        
        # Print which files the AI is looking at
        for i, doc in enumerate(docs):
            source = doc.metadata.get('source', 'Unknown')
            print(f"   Snippet {i+1} source: {source}")

        if not docs:
            context = "No relevant information found in the database."
        else:
            # CLEANUP: This removes the long "E:/Python Projects/..." path 
            # so the AI only sees the filename (e.g., [Source: fee_structure.pdf])
            context = ""
            for d in docs:
                full_path = d.metadata.get('source', 'Unknown')
                file_name = os.path.basename(full_path)
                context += f"\n\n[Source: {file_name}]\n{d.page_content}"

        # 4. Better Prompt (The "Don't Give Up" Instruction)
        prompt = f"""
        You are GCUF Envoy, a helpful university assistant. 
        Use the following snippets from the Prospectus, Fee Structure, and Admission documents to answer.
        
        RULES:
        1. If the information is in the text, provide a detailed answer.
        2. If you see a source labeled 'fee_structure', use that for money questions.
        3. Only say you don't know if the information is truly missing from the data below.

        DOCUMENTS:
        {context}

        QUESTION: {query}
        ANSWER:"""
        
        print("🤖 Gemma is generating response...")
        answer = llm.invoke(prompt)
        print("✅ Response sent to phone.")
        
        return {"response": answer}

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return {"response": f"Internal Server Error: {str(e)}"}

if __name__ == "__main__":
    print("🚀 GCUF Envoy Brain is LIVE!")
    uvicorn.run(app, host="0.0.0.0", port=8000)