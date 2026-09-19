import re
import json
import os

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

app = Flask(__name__)


# =========================================================
# COLLEGE DATA (SOURCE OF TRUTH) - plain data, not questions
# =========================================================
COLLEGE_NAME = "Chalisgaon Education Society's B.P.Arts, S.M.A.Science & K.K.C.Commerce College Chalisgaon"
DEPARTMENT = "Department of Computer Science"
ACADEMIC_YEAR = "2026-27"
LIBRARY_TIMING = "7:30 AM to 12:00 PM"
HOD_NAME = "Dr. M. V. Bildikar Sir"
WEBSITE = "cesasc.ac.in"

SEM5_COURSES = [
    "CS-311 Software Engineering",
    "CS-312 Python Programming-I",
    "CS-313 Java Programming-I",
    "CS-314 RDBMS (PostgreSQL)",
    "CS-315 Theoretical Computer Science",
    "CS-316 Lab on Python Programming-I and RDBMS (PostgreSQL)",
    "CS-317 Lab on Java Programming-I",
    "CS-318(C) Introduction to Data Science",
    "CS-319(C) Lab on Data Science",
    "CS-320 Application based Software Tools",
]

SEM6_COURSES = [
    "CS-321 Operating System",
    "CS-322 Python Programming-II",
    "CS-323 Java Programming-II",
    "CS-324 MongoDB",
    "CS-325 Lab on MongoDB & Python Programming-II",
    "CS-326 Lab on Java Programming-II",
    "CS-327(C) Introduction to Large Language Models",
]

TIMETABLE = {
    "monday": [
        "07:30 AM - CS 315: Theoretical Computer Science",
        "08:30 AM - CS 314: RDBMS",
        "09:45 AM - CS 312: Python",
        "10:45 AM - CS 317: Java Programming Lab",
    ],
    "tuesday": [
        "07:30 AM - CS 315: Theoretical Computer Science",
        "08:30 AM - CS 314: RDBMS",
        "09:45 AM - CS 312: Python",
        "10:45 AM - CS 317: Java Programming Lab",
    ],
    "wednesday": [
        "07:30 AM - CS 318(C): Introduction to Data Science",
        "08:30 AM - CS 320: Application based Software Tools",
        "09:45 AM - CS 316 Lab",
        "10:45 AM - CS 316 Lab",
    ],
    "thursday": [
        "07:30 AM - CS 318(C): Introduction to Data Science",
        "08:30 AM - CS 320: Application based Software Tools",
        "09:45 AM - CS 316 Lab",
        "10:45 AM - CS 316 Lab",
    ],
    "friday": [
        "07:30 AM - CS 313: Java Programming-I",
        "08:30 AM - CS 311: Software Engineering",
        "09:45 AM - CS 310(A): Field Project",
        "10:45 AM - CS 319(C): Lab",
    ],
    "saturday": [
        "07:30 AM - CS 313: Java Programming-I",
        "08:30 AM - CS 311: Software Engineering",
        "09:45 AM - CS 310(A): Field Project",
        "10:45 AM - CS 319(C): Lab",
    ],
}

SUBJECT_TIMING = {
    "python": "Python Programming-I (CS 312) is scheduled at 09:45 AM on Monday and Tuesday.",
    "rdbms": "RDBMS (CS 314) is scheduled at 08:30 AM on Monday and Tuesday.",
    "java": "Java Programming-I (CS 313) is scheduled at 07:30 AM on Friday and Saturday.",
    "software engineering": "Software Engineering (CS 311) is scheduled at 08:30 AM on Friday and Saturday.",
}

NOT_AVAILABLE_MSG = "Sorry, this information is not available in my current college database."

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Small, generic "when/what time" signal words (English + common Roman
# Marathi). These are combined with a SUBJECT name, never used alone,
# so they can't misfire on unrelated questions.
TIME_WORDS = {"when", "time", "timing", "lecture", "schedule", "period", "slot", "class", "kadhi"}


# =========================================================
# LOAD FAQ DATA (exam / scholarship / admission / misc)
# =========================================================
FAQ_PATH = os.path.join(os.path.dirname(__file__), "data", "college_faq.json")
try:
    with open(FAQ_PATH, "r", encoding="utf-8") as file:
        faq_data = json.load(file)
except Exception:
    faq_data = {}

# Anchor word that must be present for us to even consider a given FAQ
# category - this is what stops an unrelated word (like "college") from
# ever pulling in an answer from the wrong category.
FAQ_CATEGORY_ANCHORS = {
    "exam": ["exam"],
    "scholarship": ["scholarship"],
    "admission": ["admission"],
}

ROMAN_MARATHI_MAP = {
    "kadhi": "कधी",
    "bharaicha": "भरायचा",
    "bharaycha": "भरायचा",
    "kuthe": "कुठे",
    "konte": "कोणते",
    "milel": "मिळेल",
}


# =========================================================
# NORMALIZATION / TOKENIZATION
# =========================================================
def clean_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.
    Periods/apostrophes are removed WITHOUT adding a space, so
    'H.O.D' / "H.O.D's" become 'hod' (one token) instead of splitting
    into 'h o d'. Other punctuation becomes a space so words don't get
    glued together."""
    text = text.lower()
    text = text.replace(".", "").replace("'", "")
    text = re.sub(r"[^a-z0-9\u0900-\u097F\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def to_devanagari(text: str) -> str:
    """Best-effort conversion of common Roman-Marathi words to
    Devanagari, used only when comparing against the Devanagari
    questions already stored in college_faq.json."""
    for roman, devanagari in ROMAN_MARATHI_MAP.items():
        text = text.replace(roman, devanagari)
    return text


def contains_phrase(text: str, phrases) -> bool:
    return any(phrase in text for phrase in phrases)


def contains_token(tokens: set, words) -> bool:
    return any(w in tokens for w in words)


# =========================================================
# STRUCTURED FIELD MATCHING (fast, reliable, checked first)
# =========================================================
def find_structured_answer(cleaned: str, tokens: set):
    # --- College name ---
    if contains_phrase(cleaned, [
        "college name", "name of my college", "name of the college",
        "which college", "college cha nav", "college che nav",
        "collage name",
    ]):
        return f"Your college name is {COLLEGE_NAME}."

    # --- HOD --- (single distinctive token, matched as a whole word
    # after punctuation stripping, so "H.O.D", "h.o.d", "HOD" all work)
    if contains_token(tokens, ["hod"]) or contains_phrase(cleaned, ["head of department", "head of the department"]):
        return f"The HOD of the {DEPARTMENT} is {HOD_NAME}."

    # --- Website ---
    if contains_token(tokens, ["website"]):
        return f"The official college website is {WEBSITE}."

    # --- Semester course lists ---
    # Check VI/6 before V/5: "semester vi" contains the substring
    # "semester v", so checking V first would misfire on VI.
    if contains_phrase(cleaned, ["semester vi", "sem vi", "semester 6", "sem 6", "6th semester"]):
        return "Semester VI (T.Y. B.Sc. Computer Science) courses:\n" + "\n".join(SEM6_COURSES)

    if contains_phrase(cleaned, ["semester v", "sem v", "semester 5", "sem 5", "5th semester"]):
        return "Semester V (T.Y. B.Sc. Computer Science) courses:\n" + "\n".join(SEM5_COURSES)

    # --- Library ---
    if contains_token(tokens, ["library"]) or "लायब्ररी" in cleaned:
        return f"The college library timing is {LIBRARY_TIMING}."

    # --- Weekday timetable (weekday token + a "schedule-ish" token) ---
    for day in WEEKDAYS:
        if day in tokens and contains_token(tokens, ["timetable", "schedule", "class", "period"]):
            if day not in TIMETABLE:
                return NOT_AVAILABLE_MSG
            return f"{day.capitalize()} timetable:\n" + "\n".join(TIMETABLE[day])

    # --- Subject timing (subject token + a "when/time" token) ---
    if "software" in tokens and "engineering" in tokens and tokens & TIME_WORDS:
        return SUBJECT_TIMING["software engineering"]

    if contains_token(tokens, ["python"]) and tokens & TIME_WORDS:
        return SUBJECT_TIMING["python"]

    if contains_token(tokens, ["rdbms"]) and tokens & TIME_WORDS:
        return SUBJECT_TIMING["rdbms"]

    if contains_token(tokens, ["java"]) and tokens & TIME_WORDS:
        return SUBJECT_TIMING["java"]

    # --- General timetable (no specific day mentioned) ---
    if contains_token(tokens, ["timetable", "schedule"]):
        return (
            "The T.Y. B.Sc. Computer Science timetable is effective from "
            f"01 July 2026 for Academic Year {ACADEMIC_YEAR}. "
            "Ask me about a specific day (e.g. 'Monday timetable') or a "
            "subject (e.g. 'When is Python?') for the exact timing."
        )

    return None


# =========================================================
# FAQ MATCHING (exam / scholarship / admission)
# Anchor-gated: we only look inside a category if its anchor word
# (e.g. "exam") is present, so a generic shared word can never pull
# in an answer from an unrelated category.
# =========================================================
STOPWORDS = {
    "what", "is", "are", "the", "a", "an", "of", "for", "to", "my", "do",
    "does", "i", "in", "on", "at", "when", "where", "which", "who", "kay",
    "ahe", "che", "cha", "ची", "चा", "काय", "आहे", "college", "computer",
    "department", "science",
}


def significant_words(text: str):
    return {w for w in text.split() if len(w) > 1 and w not in STOPWORDS}


def find_faq_answer(cleaned: str, tokens: set):
    if not faq_data:
        return None

    devanagari = to_devanagari(cleaned)
    query_words = significant_words(cleaned) | significant_words(devanagari)

    for category, anchors in FAQ_CATEGORY_ANCHORS.items():
        if category not in faq_data:
            continue
        if not (tokens & set(anchors)):
            continue  # anchor word absent - skip this category entirely

        best_item = None
        best_score = -1
        for item in faq_data[category]:
            item_words = significant_words(item.get("question", "").lower())
            score = len(query_words & item_words)
            if score > best_score:
                best_score = score
                best_item = item

        if best_item:
            return best_item["answer"]

    return None


# =========================================================
# CONTEXT TEXT GIVEN TO GEMINI (single source of truth, reused)
# =========================================================
def build_faq_context_text() -> str:
    lines = []
    for category, items in faq_data.items():
        for item in items:
            q = item.get("question", "")
            a = item.get("answer", "")
            if q and a:
                lines.append(f"Q: {q}\nA: {a}")
    return "\n".join(lines)


college_context = f"""
College Name:
{COLLEGE_NAME}

Department:
{DEPARTMENT}

Academic Year:
{ACADEMIC_YEAR}

T.Y. B.Sc. Computer Science - Semester V Courses:
{chr(10).join(SEM5_COURSES)}

Semester VI Courses:
{chr(10).join(SEM6_COURSES)}

Library Timing:
{LIBRARY_TIMING}

HOD of Computer Department:
{HOD_NAME}

Official College Website:
{WEBSITE}

Weekly Timetable (T.Y. B.Sc. Computer Science, effective 01 July 2026):
Monday: {" | ".join(TIMETABLE["monday"])}
Tuesday: {" | ".join(TIMETABLE["tuesday"])}
Wednesday: {" | ".join(TIMETABLE["wednesday"])}
Thursday: {" | ".join(TIMETABLE["thursday"])}
Friday: {" | ".join(TIMETABLE["friday"])}
Saturday: {" | ".join(TIMETABLE["saturday"])}

Additional College FAQ Data:
{build_faq_context_text()}
"""


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat")
def chat():
    return render_template("chat.html")


@app.route("/test")
def test():
    return render_template("test.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    raw_question = (data.get("question") or "").strip()

    if not raw_question:
        return jsonify({"answer": "Please type a question so I can help you 🙂"})

    cleaned = clean_text(raw_question)
    tokens = set(cleaned.split())

    # 1) Fast, reliable structured field matching (college name, HOD,
    #    website, library, semester lists, timetable, subject timing)
    structured = find_structured_answer(cleaned, tokens)
    if structured:
        return jsonify({"answer": structured})

    # 2) Anchor-gated FAQ matching (exam / scholarship / admission)
    faq_answer = find_faq_answer(cleaned, tokens)
    if faq_answer:
        return jsonify({"answer": faq_answer})

    # 3) Anything else goes to Gemini, grounded in the full college
    #    context (including the FAQ data above). Gemini itself decides
    #    whether this is a general CS question (answer normally) or a
    #    college-specific question with no matching data (say it's not
    #    available) - it must never invent college-specific facts.
    prompt = f"""
You are an AI College Helpdesk assistant for this specific college.

COLLEGE INFORMATION (the only source of truth for facts about THIS college):
{college_context}

STUDENT QUESTION:
{raw_question}

RULES:
1. If the question is about THIS college specifically (its name, department, HOD,
   library, timetable, courses, website, exams, scholarships, admissions, canteen,
   hostel, fees, transport, faculty, or anything else about this institution),
   answer ONLY using facts that are literally present in the COLLEGE INFORMATION
   above - even if the wording of the question is different from the wording above.
2. If such a college-specific detail is NOT present in the COLLEGE INFORMATION
   above, reply with EXACTLY this sentence and nothing else:
   "Sorry, this information is not available in my current college database."
   Do not use outside knowledge to guess or fill the gap.
3. If the question is a general Computer Science / technology concept question
   that is not about this specific college (e.g. "What is AI?", "Why is Python
   useful?"), answer it normally and helpfully using your own knowledge.
4. Never invent facts about this college.
5. Keep answers short, clear, and student-friendly.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        answer_text = getattr(response, "text", None) or NOT_AVAILABLE_MSG
    except Exception:
        answer_text = (
            "Sorry, I couldn't reach the AI service right now. "
            "Please try again in a moment."
        )

    return jsonify({"answer": answer_text})


if __name__ == "__main__":
    app.run(debug=True)