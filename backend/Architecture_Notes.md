Project Overview:

- GCUF Envoy is an AI-powered university assistant designed to answer student queries related to Government College University Faisalabad (GCUF). The system provides information about admissions, fee structures, academic programs, university policies, and general university-related information using Retrieval-Augmented Generation (RAG).

System Architecture:
User Query
↓
FastAPI Endpoint
↓
Cache Check
↓
Query Classification (Fee / Admission / General)
↓
Metadata-Based Filtering
↓
ChromaDB Retrieval (MMR Search)
↓
Context Formatting
↓
Groq LLM (Llama 3.3 70B)
↓
Response Generation
↓
Response Caching
↓
Return Response to Client

Ingestion Pipeline:
Data(PDF) -> Extraction(PDFplumber) -> Chunking(RecursiveTextsplitter) -> Embedding generation(along metadata) -> chromaDB Storage.

Loader.py Explanation:

Logging:

- Every execution is logged.
  Extraction:
- Pdfplumber is used extract data from pdfs. First the tables are extracted in the from rows in key-value pairs and then the normal text is extracted and combined with table text.
  Text splitter:
- Recursive text splitter is used to split the text into chunks along with its metadata. <Table> </Table> tags are used so that split doesnt happen from mid of the table. There are 800 chars per chunk with 150 char overlap. Seperators are used to split the content Paragraph by pargraph, sentence by sentence, word by word and at the last resort character by character.
  Embeddings:
- Embeddings are made using miniLM. 384 dimentional vectors are normalized with length 1 for easier chromadb retrieval.
  Metadata:
  Each chunk is stored with metadata including:

- source
- page number
- file name
  Purpose:
  Metadata allows filtering and retrieval from specific university documents during query processing. It also helps trace generated answers back to their source documents.
  Exception handling: Exceptions are handled for every module.

Design Choices:

Pdfplumber:

- For better table extraction.
  MiniLM:
- 22 million parameters, faster and efficient for these types of projects.
  ChromaDB:
- Runs fully locally, no external infrastructure,
  disk persistent, LangChain native. Tradeoff: doesn't scale
  horizontally across multiple servers.
  RecursiveTextSplitter:
- Chosen over fixed-size splitter because
  it respects natural text boundaries. Custom separators prioritize
  table boundaries to prevent mid-table splits.
  Chunk Overlap (150 chars):
- Safety margin ensuring sentences
  near chunk boundaries aren't lost across splits.
  Batch Size (500):
- Prevents RAM spikes during embedding generation
  and ChromaDB writes.
  Full Rebuild Strategy:
- loader.py deletes and rebuilds ChromaDB
  from scratch on every run. Simpler and safer for a system that
  updates once per semester. Tradeoff: expensive for incremental updates.

Current Limitations:

- Metadata is basic (source, page, file_name only)
- No automatic document categorization
- Chunk size is hardcoded
- No evaluation of chunk quality
- No duplicate chunk detection
- Full rebuild on every loader.py run — no incremental ingestion
- Windows/Linux path separator inconsistency (fixed with os.path.join)
- No persistent cache — response cache lost on server restart
- Hardcoded CS keyword list for routing — brittle and unmaintainable
- Embedding model is tightly coupled to ChromaDB contents —
  changing models requires full database rebuild

Loader.py Responsibilities:

- Read the PDF.
- Extract the text and table contents.
- Convert extracted content into chunks.
- Generate embeddings for each chunk.
- Add metadata to each chunk.
- Store embedding and metadata in chromaDB.
- Rebuild the database when univeristy PDF's change or new PDF is added.

Main.py Explanation:

Logging:

- Just like loader.py we use logging for every method's execution.
  Configuration:
- Setting up all variables.
  Lifespan:
- Load everything we need before working on query. i.e LLM, chromaDb and make the server live.
  FASTAPi App:
- Gives app its title and description with its life span, CORS is used to let through the query from mismatched ports, its better for testing for now.
  Cached responses:
- Check chached responses if the question is asked again answer directly from here. Its in the form of md5 hash.
  Ask Groq def:
- It has 3 arguements the system and user queary and max-tokens which is 1024 here bt overriden later.
- System query are rules LLM follow and user query is the question user asked.
- Temprature is set to 0.1 so it gives the factual response rather then creative.
- The first response is selected because it usually the best one.
  Classifier:
- Groq gives one word answer which used 5 tokens, the response is give on the bases of user and system query. This response classifies as if the question is about fee it finds it in fee document objects and same about admssion policies and prospectus.
  Fetching:
- MMR is used instead of exact matching to get behind meaning of the query. MMR gives 6 related document objects accross all documents. And then its filtered to use only the chunks from the classified document.
- Fallback if theres no content in the chunks LLM falls back to specified document objects Page 1-6 to give the response from.
  Building Context:
- The relevant chunks are grouped together along with the metadata(files_name, page_num) and formatted to text string which LLM can read. LLM don't only respond with Refrences but the actual content inside.
  Prompts:
- System prompts/rules are different fro diffrent query type for better responses. LLM acts diffrently for every query to minimize the usuage of data its trained with and give relevant answers only from the documents.
  Exception handling:
- Exceptions are handled using Error: 400 and Error: 500 so that LLM gives graceful responses if it didnt find the relevant data instead of hallucinating and giving no response at all.
  Return:
- The result is stored in cache and returned to the user through app.
  App.health:
- Used to check the server status and cached storage for how many responses are stored in it.

Design Choices:

Groq:

- Groq api is used instead of a local llm for faster responses regardless of the hardware limitaions.
  Cache:
- So that LLM dont have to work twice for the same question.
- "Query is normalized with .lower() and .strip() before hashing — so 'What is BS CS fee?' and 'what is bs cs fee?' produce the same hash and hit the same cache entry."
  Lifespan:
- Modules are loaded at the start instead of as per query requirment for faster responses.
  Logging:
- To keep track of the execution and resolve bugs if it arrives so we dont have to got through every line of code.
  CORS:
- As we still are in the development phase we allow requests from mismatch ports which is a security risk but fine for testing the system for now.
  Query Classifier:
- TO filter out from which document to respond from which query instead of getting the messy data from all over 22600+ chunks.
- Max 5 tokens are used to get only one word from LLM to classify the query type.
  MMR:
- Used mmr to get to the meaning behind the query instead of just words matching. MMR gives the most relevant AND diverse 6 chunks. The diversity part is what separates it from plain similarity search.
- Fallback used if theres no content in mmr given chunks we use the selected pages to respond from classified document.
- After getting 6 document objects using MMR from across all documents we only select the ones from classified document.
- At last one chunk from different document is added to give more context to LLM.
- Only one chunk is used to prevent hallucination and data mess.
  Rules/ System Queries:
- 3 types of rules are used for 3 types of quries fee, admssion and prospectus, for fee we need the factual answers, for admission we need the policies, and from prospectus we need the history faculy, so it cannot be done with same system prompts. This is to prevent hallucination and pretrained data usuage from LLM.
  Exceptions:
- So that LLM dont give no answer or irrelevant answer if it didnt find any, we used exception handling to respond gracefully that it didnt find the data.
  App.health:
- To check the storage of cached responses and status of the server.

Main.py Responsibilities:

- Gets User Query
- Setup Configuration
- Load LLM and chromaDB
- Classify query using LLM.
- MMR gives relevant chunks to the query
- Chunks are filtered and formatted for LLM to read.
- LLM responds using the data, system query and user query.
- Give content reponses instead of just refrences.
- Reponse is returned to Flutter app and stored in cache.

Limitaions:

- Everytime system restarts the cache is deleted.
- MMR searches through all the chunks.
- LLM is used as classifier, a local classifier would be faster.
- fetch_from_source() loads entire source PDF into memory
  then filters manually — bypasses ChromaDB's native filtering
  Phase 2 fix: compound metadata filters directly on ChromaDB engine

v1.0 — Initial deployment on Azure

- print statements for logging
- Global variables for embeddings and ChromaDB
- Hardcoded API key fallback
- chunk_size = 1000

v2.0 — Polished version (current)

- Replaced print with logging module
- Moved resources to app.state via lifespan pattern
- Added type hints throughout
- Reduced chunk_size to 800
- Added file_name to metadata
- Secured API key via .env
- Fixed Windows path separator bug

Phase 2: Day 1

- Created config.py with metadata keyword mappings (FACULTY_KEYWORDS, 
  DEGREE_KEYWORDS, FEE_QUERY_KEYWORDS, ADMISSION_QUERY_KEYWORDS)
- Added detection functions: detect_from_keywords(), detect_faculty(), 
  detect_degree(), detect_query_type()
- detect_query_type() replaces the Groq LLM classifier — 
  no API call needed for classification anymore
- fetch_relevant_chunks() replaces fetch_from_source() — 
  ChromaDB now filters at engine level using compound metadata filters
  instead of loading entire source PDFs into memory
- New metadata fields added to every chunk at ingestion: 
  category, faculty, degree_level, content_type
