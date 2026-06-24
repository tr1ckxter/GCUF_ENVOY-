import os
import hashlib
import logging
from contextlib import asynccontextmanager
from tkinter.filedialog import test
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from groq import Groq
import uvicorn
from dotenv import load_dotenv
load_dotenv() 

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL   = "sentence-transformers/all-MiniLM-L6-v2"
GROQ_MODEL        = "llama-3.3-70b-versatile"
PERSIST_DIRECTORY = "./db"
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")

FEE_SOURCE        = os.path.join(".", "data", "Fee-Structure-2025.pdf")
ADMISSION_SOURCE  = os.path.join(".", "data", "Admission-Policy-2025-26.pdf")
PROSPECTUS_SOURCE = os.path.join(".", "data", "Prospectus-2025-v1.pdf")

CS_KEYWORDS = [
    "software", "computer science", "information technology",
    "data science", "data analytics", "bs cs", "bscs", "bsse", "bsit"
]

# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load heavy resources once at startup instead of per request.
    FastAPI lifespan replaces the deprecated @app.on_event("startup") pattern.
    """
    logger.info("=" * 50)
    logger.info("GCUF Envoy — Starting up")
    logger.info("=" * 50)

    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY environment variable is not set.")
        raise RuntimeError("GROQ_API_KEY is required.")

    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    app.state.embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    logger.info(f"Loading ChromaDB from: {PERSIST_DIRECTORY}")
    app.state.vector_db = Chroma(
        persist_directory=PERSIST_DIRECTORY,
        embedding_function=app.state.embeddings
    )

    logger.info(f"Initializing Groq client with model: {GROQ_MODEL}")
    app.state.groq_client = Groq(api_key=GROQ_API_KEY)

    app.state.response_cache = {}

    logger.info("✅ Startup complete. Ready to serve requests.")
    logger.info("=" * 50)

    yield

    logger.info("GCUF Envoy — Shutting down.")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="GCUF Envoy API",
    description="AI-powered FAQ assistant for Government College University Faisalabad.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Core functions ────────────────────────────────────────────────────────────
def get_cache_key(query: str) -> str:
    """Generate a consistent MD5 hash key for caching query responses."""
    return hashlib.md5(query.strip().lower().encode()).hexdigest()


def ask_groq(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024
) -> str:
    """
    Send a prompt to the Groq API and return the response text.

    Args:
        system_prompt: Defines the assistant's role and behavior.
        user_prompt: The actual question and context to answer.
        max_tokens: Maximum tokens in the response.

    Returns:
        The LLM's response as a string.

    Raises:
        Exception: If the Groq API call fails.
    """
    response = app.state.groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return response.choices[0].message.content


def detect_query_type(query: str) -> str:
    """
    Classify an incoming query into one of three categories using the LLM.

    Uses a minimal prompt with max_tokens=5 to keep classification fast
    and cheap. Falls back to 'general' if the response is ambiguous.

    Args:
        query: The raw user question.

    Returns:
        One of: 'fee', 'admission', 'general'
    """
    system = "You are a classifier. Reply with exactly one word only: fee, admission, or general."
    user = f"""fee = fees, tuition, charges, costs, payment, how much, total fee, semester fee
admission = applying, eligibility, merit, deadlines, requirements, enrollment, entry test
general = history, departments, programs, facilities, campus, courses, vision, mission, faculty

Question: {query}
Category:"""

    result = ask_groq(system, user, max_tokens=5).strip().lower()
    logger.info(f"  Query classified as: '{result}'")

    if "fee" in result:
        return "fee"
    elif "admission" in result:
        return "admission"
    else:
        return "general"


def fetch_from_source(
    source_path: str,
    query: str,
    fallback_pages: Optional[list] = None
) -> tuple[list[Document], list[Document]]:
    """
    Retrieve relevant document chunks from a specific source PDF.

    Uses ChromaDB metadata filtering to scope retrieval to the correct
    file, then uses MMR similarity search to identify relevant pages.
    For CS/SE queries, forces inclusion of page 2 where BS program
    fees are located.

    Args:
        source_path: Exact source path as stored in ChromaDB metadata.
        query: User query used for similarity search.
        fallback_pages: Pages to use if similarity search returns nothing.

    Returns:
        Tuple of (filtered_docs, all_similar_docs).
    """
    all_data = app.state.vector_db.get(
        where={"source": {"$eq": source_path}},
        include=["documents", "metadatas"]
    )

    similar_docs = app.state.vector_db.max_marginal_relevance_search(
        query, k=6, fetch_k=20
    )

    relevant_pages = set(
        d.metadata.get("page")
        for d in similar_docs
        if d.metadata.get("source") == source_path
    )

    # Fee tables for BS CS/SE/IT programs are always on page 2


    logger.info(f"  Relevant pages in {os.path.basename(source_path)}: {relevant_pages}")

    if not relevant_pages and fallback_pages:
        relevant_pages = set(fallback_pages)

    docs = [
        Document(page_content=doc, metadata=meta)
        for doc, meta in zip(all_data["documents"], all_data["metadatas"])
        if meta.get("page") in relevant_pages
    ]

    return docs, similar_docs


def build_context(docs: list[Document]) -> str:
    """
    Format retrieved document chunks into a structured context string.
    Groups chunks by source file with clear section headers.

    Args:
        docs: List of Document objects from ChromaDB retrieval.

    Returns:
        Formatted string ready to be injected into the LLM prompt.
    """
    grouped: dict[str, list[str]] = {}

    for doc in docs:
        file_name = os.path.basename(doc.metadata.get("source", "Unknown"))
        page = doc.metadata.get("page", "?")
        if file_name not in grouped:
            grouped[file_name] = []
        grouped[file_name].append(f"[Page {page}]\n{doc.page_content}")

    return "\n\n".join(
        f"=== SOURCE: {file_name} ===\n" + "\n\n".join(pages)
        for file_name, pages in grouped.items()
    )


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Check server status and active model."""
    return {
        "status": "live",
        "model": GROQ_MODEL,
        "cache_size": len(app.state.response_cache)
    }


@app.post("/query")
async def ask_question(request: Request):
    """
    Main RAG endpoint. Accepts a JSON body with a 'query' field.
    Routes the query to the correct document source, retrieves
    relevant chunks, and generates a grounded response via Groq.

    Request body:
        {"query": "What is the fee for BS Software Engineering?"}

    Returns:
        {"response": "..."}
    """
    try:
        data = await request.json()
        query = data.get("query", "").strip()

        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty.")

        logger.info(f"Incoming query: '{query}'")

        # Return cached response if available
        cache_key = get_cache_key(query)
        if cache_key in app.state.response_cache:
            logger.info("  Cache hit — returning cached response")
            return {"response": app.state.response_cache[cache_key]}

        query_type = detect_query_type(query)

        if query_type == "fee":
            docs, similar_docs = fetch_from_source(
                FEE_SOURCE, query,
                fallback_pages=list(range(1, 6))
            )
            extra = [d for d in similar_docs if d.metadata.get("source") != FEE_SOURCE]
            docs = docs + extra[:1]

            system_prompt = (
                "You are GCUF Envoy, the official fee assistant for Government College "
                "University Faisalabad. You provide accurate fee information from official "
                "documents only."
            )
            user_prompt = f"""Answer the student's fee question using ONLY the fee tables below.

RULES:
1. Read every [TABLE] block — each line = one semester.
2. Present as a clear breakdown:
   • Semester 1: Rs. X (Admission: X | Registration: X | Tuition: X | Exam: X | Other: X)
   • Semester 2: Rs. X
   • Total Fee: Rs. X
3. Always include Total Fee at the end.
4. State which program and faculty the fees belong to.
5. NEVER say "refer to page" — write the actual numbers.
6. NEVER invent numbers.
7. If not found say: "Fee information for this program was not found. Please contact the Accounts Office at GCUF or visit www.gcuf.edu.pk"

FEE DOCUMENTS:
{build_context(docs)}

STUDENT QUESTION: {query}

Complete fee breakdown:"""

        elif query_type == "admission":
            docs, similar_docs = fetch_from_source(
                ADMISSION_SOURCE, query,
                fallback_pages=list(range(1, 8))
            )
            extra = [d for d in similar_docs if d.metadata.get("source") != ADMISSION_SOURCE]
            docs = docs + extra[:1]

            system_prompt = (
                "You are GCUF Envoy, the official admissions assistant for Government College "
                "University Faisalabad. You provide accurate admission information from "
                "official documents only."
            )
            user_prompt = f"""Answer the student's admission question using ONLY the documents below.

RULES:
1. Give a complete detailed answer — never summarize briefly.
2. For eligibility: list ALL requirements as bullet points.
3. For process: list ALL steps in numbered order.
4. For deadlines: state exact dates from the documents.
5. For merit: explain the exact calculation method.
6. NEVER say "refer to page X" — write the actual information.
7. NEVER invent policies or dates.
8. End with: "For the most current information visit www.gcuf.edu.pk"
9. If not found say: "This is not in the current admission policy. Please contact the Admissions Office at GCUF."

ADMISSION DOCUMENTS:
{build_context(docs)}

STUDENT QUESTION: {query}

Complete admission answer:"""

        else:
            docs = app.state.vector_db.max_marginal_relevance_search(
                query, k=8, fetch_k=20
            )
            system_prompt = (
                "You are GCUF Envoy, the official AI assistant for Government College "
                "University Faisalabad. You provide detailed, accurate information about "
                "the university from official documents."
            )
            user_prompt = f"""Answer the student's question in full detail using the documents below.

RULES:
1. Write a thorough complete answer — minimum 4-5 sentences.
2. NEVER say "refer to page X" or "see the document" — write the actual content out.
3. For history: include founding year, milestones, growth, and achievements.
4. For departments: describe programs, faculty strength, facilities, and research.
5. For facilities: describe what is available and how students access it.
6. Write in clear friendly paragraphs a student can easily understand.
7. If truly not in documents say: "I don't have detailed information on this. Please visit www.gcuf.edu.pk"

UNIVERSITY DOCUMENTS:
{build_context(docs)}

STUDENT QUESTION: {query}

Complete detailed answer:"""

        logger.info(f"  Using {len(docs)} chunks from retrieval")

        if not docs:
            return {"response": "I couldn't find relevant information. Please visit www.gcuf.edu.pk or contact GCUF directly."}

        logger.info("  Sending to Groq...")
        answer = ask_groq(system_prompt, user_prompt)

        app.state.response_cache[cache_key] = answer
        logger.info("  Response generated and cached.")

        return {"response": answer}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error processing query: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"response": "An internal error occurred. Please try again."}
        )


if __name__ == "__main__":
    logger.info("Starting GCUF Envoy server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
    
