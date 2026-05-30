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

print("--- 🧠 Loading Database ---")
embeddings = OllamaEmbeddings(model="nomic-embed-text")
vector_db = Chroma(persist_directory="./db", embedding_function=embeddings)
llm = OllamaLLM(model="gemma3:4b")


def build_context(docs):
    """Group chunks by source file and tag table content clearly."""
    # Group by file so the LLM sees related content together
    grouped = {}
    for doc in docs:
        full_path = doc.metadata.get("source", "Unknown")
        file_name = os.path.basename(full_path)
        page = doc.metadata.get("page", "?")
        key = file_name
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(f"[Page {page}]\n{doc.page_content}")

    context_parts = []
    for file_name, pages in grouped.items():
        context_parts.append(
            f"=== SOURCE: {file_name} ===\n" + "\n\n".join(pages)
        )
    return "\n\n".join(context_parts)


@app.post("/query")
async def ask_question(request: Request):
    try:
        data = await request.json()
        query = data.get("query", "")

        print(f"📱 Query: {query}")

        # Fetch more chunks — fee tables often span multiple rows/chunks
        docs = vector_db.max_marginal_relevance_search(query, k=10, fetch_k=30)
        print(f"📄 Retrieved {len(docs)} chunks")

        if not docs:
            return {"response": "I couldn't find relevant information in the university documents. Please rephrase your question or contact the admissions office."}

        context = build_context(docs)

        prompt = f"""You are GCUF Envoy, the official assistant for Government College University Faisalabad.
You have been given excerpts from the university's Prospectus, Fee Structure, and Admission documents.

INSTRUCTIONS:
1. Answer using ONLY the information in the documents below.
2. For fee questions: look for [TABLE] blocks — these contain the actual fee rows. Read them carefully. Present fees in a clear list format.
3. If a table row says "Tuition Fee: 15000 | Semester: Fall 2024", that means tuition is Rs. 15,000 for Fall 2024.
4. Always mention the source file and page number when quoting specific figures.
5. If the exact answer is not in the documents, say: "This specific information is not in my documents. Please contact the Admissions Office at GCUF."
6. Never guess or make up fee amounts, dates, or policies.

DOCUMENTS:
{context}

STUDENT QUESTION: {query}

ANSWER:"""

        print("🤖 Generating response...")
        answer = llm.invoke(prompt)
        print("✅ Done.")

        return {"response": answer}

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {"response": f"Internal error: {str(e)}"}


if __name__ == "__main__":
    print("🚀 GCUF Envoy Brain is LIVE!")
    uvicorn.run(app, host="0.0.0.0", port=8000)