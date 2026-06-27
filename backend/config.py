import re

# ── Metadata keyword mappings ─────────────────────────────────────────────────
FACULTY_KEYWORDS = {
    "physical_sciences": ["physical science", "computer science",
                          "software engineering", "information technology",
                          "data science", "data analytics", "mathematics",
                          "physics", "chemistry", "statistics"],
    "engineering": ["electrical engineering", "civil engineering",
                   "mechanical engineering", "chemical engineering",
                   "architectural"],
    "business": ["mba", "business administration", "commerce", "banking"],
    "life_sciences": ["botany", "zoology", "biochemistry", "microbiology"],
    "arts": ["english", "urdu", "history", "islamic studies"],
    "ms_mphil": ["m.phil", "mphil"],
}

DEGREE_KEYWORDS = {
    "bs": ["bachelor", "bs ", "4-year", "4 year", "undergraduate"],
    "ms": ["master", "ms ", "m.phil", "mphil", "2-year"],
    "phd": ["ph.d", "phd", "doctorate"],
}

FEE_QUERY_KEYWORDS = ["fee", "tuition", "charges", "cost", "payment", "how much"]
ADMISSION_QUERY_KEYWORDS = ["admission", "eligibility", "merit", "deadline", "apply", "requirements"]

# ── Detection functions ───────────────────────────────────────────────────────

def detect_query_type(query: str) -> str:
    query_lower= query.lower()
    if any(keyword in query_lower for keyword in FEE_QUERY_KEYWORDS):
        return "fee"
    elif any(keyword in query_lower for keyword in ADMISSION_QUERY_KEYWORDS):
        return "admission"
    else:
        return "general"

def detect_category(file_name: str) -> str:
    file_lower = file_name.lower()
    if "fee" in file_lower:
        return "fee"
    elif "admission" in file_lower:
        return "admission"
    else:
        return "general"

def detect_from_keywords(text: str, keyword_dict: dict) -> str:
    text_lower = text.lower()
    for label, keywords in keyword_dict.items():
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_lower):
                return label
    return "general"

def detect_faculty(text: str) -> str:
    return detect_from_keywords(text, FACULTY_KEYWORDS)

def detect_degree(text: str) -> str:
    return detect_from_keywords(text, DEGREE_KEYWORDS)