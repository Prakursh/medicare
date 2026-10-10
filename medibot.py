from llm_parser import parse_question
import re
import pandas as pd
from rapidfuzz import process, fuzz
from prescription_guard import (
    check_query,
    check_medicine
)


# ======================================
# 1. SAFETY MESSAGES
# ======================================

SAFETY_MESSAGES = {
    "emergency": (
        "🚨 **Possible medical emergency**\n\n"
        "If someone may have taken too much medicine, "
        "has difficulty breathing, or has another serious "
        "reaction, seek emergency medical assistance "
        "immediately. Do not rely on MediBot for urgent care."
    ),
    "prescription": (
        "🔒 **Prescription verification required**\n\n"
        "MediCare cannot determine legal prescription status "
        "from this dataset or authorize medicine purchases. "
        "Please verify current requirements with a licensed "
        "pharmacist. Do not attempt to bypass prescription "
        "requirements."
    ),
    "personal_medical": (
        "⚠️ **Personal medical advice restricted**\n\n"
        "I cannot determine whether a medicine is suitable "
        "for you, recommend doses or treatment, or advise "
        "changing prescribed medication. A qualified clinician "
        "or pharmacist must consider your medical situation. "
        "I can help look up recorded product information."
    ),
    "clinical_information": (
        "⚠️ **Clinical information unavailable**\n\n"
        "This medicine dataset does not contain sufficiently "
        "verified information about side effects, interactions, "
        "contraindications, or treatment effectiveness. "
        "Please consult a qualified healthcare professional "
        "or an authoritative medicine information source."
    ),
    "manipulation": (
        "⚠️ **Safety controls remain active**\n\n"
        "I cannot disable medical safety restrictions. "
        "I can still provide recorded medicine composition, "
        "pack size, manufacturer, and listed price."
    )
}


# ======================================
# 2. DETECTION PATTERNS
# ======================================

EMERGENCY_PATTERNS = [
    r"\boverdos(?:e|ed|ing)\b",
    r"\bpoison(?:ing|ed)?\b",
    r"\b(?:took|taken|swallowed|ate)\b.{0,65}"
    r"\b(?:too much|too many|extra tablets|extra pills|"
    r"more than prescribed|more than recommended)\b",
    r"\b(?:difficulty breathing|trouble breathing|"
    r"can't breathe|cannot breathe)\b",
    r"\b(?:unconscious|seizure|severe chest pain|"
    r"severe allergic reaction)\b",
]

PRESCRIPTION_PATTERNS = [
    r"\bwithout (?:a )?prescription\b",
    r"\bwithout (?:an? )?(?:rx|script)\b",
    r"\b(?:no rx|no prescription)\b",
    r"\bprescription (?:required|needed|necessary)\b",
    r"\b(?:otc|over.the.counter)\b",
    r"\b(?:buy|purchase|order|get)\b.{0,50}"
    r"\b(?:without|avoid|bypass)\b.{0,30}"
    r"\b(?:prescription|rx)\b",
]

PERSONAL_MEDICAL_PATTERNS = [
    # Dosage and medication use
    r"\bhow many\b.{0,50}\b(?:tablets?|pills?|capsules?|doses?)\b",

    r"\bhow much\b.{0,55}\b(?:take|use|give|administer|swallow)\b",

   

    r"\b(?:what|which)\b.{0,25}"
    r"\b(?:dose|dosage)\b.{0,40}\b(?:take|use|need)\b",

    r"\b(?:how often|when|how long)\b.{0,50}"
    r"\b(?:take|use|continue)\b",

    r"\b(?:can|could|should|may|must)\b.{0,65}"
    r"\b(?:take|use|mix|combine|stop|switch)\b",

    r"\b(?:how to|tell me how to)\b.{0,35}"
    r"\b(?:take|use|inject|administer)\b",

    # Personal safety
    r"\b(?:safe|okay|ok|suitable)\b.{0,45}"
    r"\b(?:for me|for my|with|during|while)\b",

    r"\b(?:pregnan\w*|breastfeed\w*|nursing|"
    r"infant|baby|toddler)\b",

    r"\b(?:child|children|teenager|"
    r"\d{1,2}.years?.old|"
    r"\d{1,2}.yr.old)\b",

    r"\b(?:my other medicine|my medication|"
    r"other drugs|other tablets)\b",

    # Treatment and diagnosis
    r"\b(?:what|which|recommend|suggest)\b.{0,55}"
    r"\b(?:medicine|medication|drug|treatment)\b"
    r".{0,45}\b(?:for|should i|to treat)\b",

    r"\b(?:diagnose|diagnosis|treat my|"
    r"cure my|change my dose|increase my dose|"
    r"reduce my dose|stop taking)\b",

    r"\b(?:i have|i'm having|i am having)\b.{0,45}"
    r"\b(?:fever|headache|infection|pain|"
    r"cough|symptoms)\b",
]

CLINICAL_INFORMATION_PATTERNS = [
    r"\bside.effects?\b",
    r"\bdrug.interactions?\b",
    r"\binteractions?\b",
    r"\bcontraindications?\b",
    r"\ballerg(?:y|ies|ic)\b",
    r"\b(?:effective|effectiveness|efficacy)\b",
    r"\b(?:warnings|precautions)\b",
]

MANIPULATION_PATTERNS = [
    r"\bignore\b.{0,55}"
    r"\b(?:safety|rules|restrictions|instructions)\b",
    r"\b(?:disable|bypass|remove)\b.{0,45}"
    r"\b(?:guardrails|safety|restrictions)\b",
    r"\bpretend\b.{0,55}"
    r"\b(?:doctor|no rules|unrestricted)\b",
]


def normalize_text(text):
    text = str(text).lower()
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def matches_any(patterns, text):
    return any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in patterns
    )


def classify_safety(question):
    q = normalize_text(question)


    q = re.sub(r"^\[\s*[xX]?\s*\]\s*", "", q)
    q = re.sub(r"^an i\b", "can i", q)
    q = re.sub(r"^gnore\b", "ignore", q)
    # Emergency detection takes priority
    if matches_any(EMERGENCY_PATTERNS, q):
        return "emergency"

    if matches_any(MANIPULATION_PATTERNS, q):
        return "manipulation"

    if matches_any(PRESCRIPTION_PATTERNS, q):
        return "prescription"

    if matches_any(PERSONAL_MEDICAL_PATTERNS, q):
        return "personal_medical"

    if matches_any(CLINICAL_INFORMATION_PATTERNS, q):
        return "clinical_information"

    return "safe_information"


def safety_check(question):
    category = classify_safety(question)

    if category == "safe_information":
        return None

    return SAFETY_MESSAGES[category]


# ======================================
# 3. INTENT DETECTION
# ======================================

def get_intent(question):
    q = normalize_text(question)

    if any(word in q for word in [
        "cheaper", "alternative", "substitute",
        "equivalent", "compare"
    ]):
        return "compare"

    if any(word in q for word in [
        "composition", "ingredient", "contains"
    ]):
        return "composition"

    if any(word in q for word in [
        "price", "cost", "expensive"
    ]):
        return "price"

    return "information"


# ======================================
# 4. MEDICINE NAME EXTRACTION
# ======================================

def extract_medicine_name(question):
    name = str(question).strip()

    # Remove copied checklist markers
    name = re.sub(
        r"^\s*\[\s*[xX]?\s*\]\s*", "", name
    )

    patterns = [
        r"^what is the price of\s+",
        r"^what is the cost of\s+",
        r"^how much does\s+",
        r"^what is the composition of\s+",
        r"^what ingredients are in\s+",
        r"^what does\s+",
        r"^tell me about\s+",
        r"^information about\s+",
        r"^find cheaper composition matches (?:to|for)\s+",
        r"^find cheaper alternatives (?:to|for)\s+",
        r"^find alternatives (?:to|for)\s+",
        r"^compare prices (?:for|of)\s+",
        r"^compare\s+",
        r"^find the price of\s+",
        r"^price of\s+",
        r"^composition of\s+",
        r"^ingredients in\s+",
        r"^search for\s+",
        r"^search\s+",
        r"^what is\s+",
        r"^find\s+",
    ]

    for pattern in patterns:
        updated = re.sub(
            pattern, "", name,
            count=1, flags=re.IGNORECASE
        )
        if updated != name:
            name = updated
            break

    name = re.sub(
        r"\s+(?:cost|price|contain|contains)\??$",
        "", name, flags=re.IGNORECASE
    )

    return name.strip(" ?.,!")


# ======================================
# 5. DATASET SEARCH
# ======================================

def find_medicine(name, df):
    target = normalize_text(name)

    if not target:
        return None, []

    exact = df[df["name_search"] == target]

    if len(exact) == 1:
        return exact.iloc[0], []

    if len(exact) > 1:
        return None, exact["name"].head(5).tolist()

    matches = df[
        df["name_search"].str.startswith(
            target, na=False
        )
    ]

    if matches.empty:
        matches = df[
            df["name_search"].str.contains(
                target, regex=False, na=False
            )
        ]

    if len(matches) == 1:
        return matches.iloc[0], []

    if len(matches) > 1:
        return None, (
            matches["name"]
            .drop_duplicates()
            .head(5)
            .tolist()
        )

    suggestions = process.extract(
        name,
        df["name"].drop_duplicates().tolist(),
        scorer=fuzz.WRatio,
        limit=3,
        score_cutoff=80
    )

    return None, [item[0] for item in suggestions]


# ======================================
# 6. INFORMATION RETRIEVAL
# ======================================

def medicine_information(m):
    c1 = str(m["short_composition1"]).strip()
    c2 = str(m["short_composition2"]).strip()

    composition = ", ".join(
        x for x in [c1, c2] if x
    ) or "Not recorded"

    price = m["price_numeric"]

    price_text = (
        f"₹{price:.2f}"
        if pd.notna(price) else "Unavailable"
    )

    status = (
        "Marked discontinued"
        if m["discontinued"]
        else "Not marked discontinued in dataset"
    )

    return (
        f"### {m['name']}\n\n"
        f"**Manufacturer:** {m['manufacturer_name']}\n\n"
        f"**Composition:** {composition}\n\n"
        f"**Pack:** {m['pack_size_label']}\n\n"
        f"**Listed price:** {price_text}\n\n"
        f"**Dataset status:** {status}\n\n"
        "Source: Local Indian Medicine Dataset. "
        "Information and prices may be outdated. "
        "This record does not verify clinical suitability "
        "or prescription status."
    )


# ======================================
# 7. COMPOSITION MATCHING
# ======================================

def compare_medicines(m, df):
    if not str(m["short_composition1"]).strip():
        return "Composition data is insufficient."

    if not str(m["pack_size_label"]).strip():
        return "Pack-size data is insufficient."

    if m["discontinued"]:
        return (
            "This product is marked discontinued "
            "in the dataset. Please ask a licensed "
            "pharmacist about current options."
        )

    matches = df[
        (df["composition_key"] == m["composition_key"])
        & (df["pack_key"] == m["pack_key"])
        & (~df["discontinued"])
        & df["price_numeric"].notna()
        & (df["price_numeric"] > 0)
        & (df["name"] != m["name"])
    ].sort_values("price_numeric")

    if matches.empty:
        return (
            "No other records with the same listed "
            "composition and pack-size label were found."
        )

    answer = (
        f"### Composition matches for {m['name']}\n\n"
        "The following records match the dataset's "
        "composition and pack-size fields. **They are not "
        "verified interchangeable products.**\n\n"
    )

    for _, row in matches.head(5).iterrows():
        answer += (
            f"- **{row['name']}** — "
            f"₹{row['price_numeric']:.2f} "
            f"({row['manufacturer_name']})\n"
        )

    answer += (
        "\n⚠️ **Do not substitute medicines based on "
        "this comparison.** A pharmacist or clinician "
        "must verify dosage form, strength, release "
        "mechanism, route, and clinical suitability. "
        "Prices may be outdated."
    )

    return answer


# ======================================
# 8. MAIN CHATBOT PIPELINE
# ======================================


def get_response(question, df):
    question = str(question).strip()

    if not question:
        return "Please enter a question."

    restricted = check_query(question)

    if restricted:
        return restricted
    # STEP 1: Local safety checks
    # These run BEFORE calling OpenRouter.
    safety = safety_check(question)

    if safety is not None:
        return safety

    # STEP 2: Handle greetings
    if normalize_text(question) in ["hi", "hello", "hey"]:
        return (
            "Hello! I'm MediBot. I can help you find "
            "medicine information, ingredients, "
            "manufacturers, and listed prices."
        )

    # STEP 3: Send question to OpenRouter
    parsed = parse_question(question)

    if parsed is not None:

        category = parsed["category"]
        intent = parsed["intent"]
        medicine_name = parsed["medicine_name"]

        # STEP 4: Apply LLM safety classification
        if category in SAFETY_MESSAGES:
            return SAFETY_MESSAGES[category]

        if category != "safe_information":
            return (
                "I couldn't safely interpret your request. "
                "Please ask about a medicine's name, "
                "composition, manufacturer, pack size, "
                "or listed price. For medical decisions, "
                "consult a qualified healthcare professional."
            )

    else:
        # STEP 5: Safe fallback if OpenRouter fails
        # Only allow basic database lookups.

        q = normalize_text(question)

        exact_name = (df["name_search"] == q).any()

        if exact_name:
            medicine_name = question
            intent = "information"

        else:
            # Strictly recognized lookup question formats
            patterns = [
                r"^what is (?:the )?price of\s+",
                r"^what is (?:the )?cost of\s+",
                r"^what is (?:the )?composition of\s+",
                r"^what ingredients are in\s+",
                r"^find the price of\s+",
                r"^find cheaper composition matches for\s+",
                r"^tell me about\s+",
            ]

            import re

            if not any(re.match(p, q) for p in patterns):
                return (
                    "OpenRouter is unavailable, and I cannot "
                    "confidently classify this request. "
                    "Please try again later or enter an "
                    "exact medicine name."
                )

            medicine_name = extract_medicine_name(question)
            intent = get_intent(question)

    # STEP 6: Check extracted medicine name
    if not medicine_name:
        return (
            "Please provide the complete medicine name."
        )

    # STEP 7: Search local medicine database
    medicine, suggestions = find_medicine(
        medicine_name, df
    )

    if medicine is not None:
        restricted = check_medicine(medicine)

        if restricted:
            return restricted

    if medicine is None:

        if suggestions:
            formatted = "\n".join(
                f"- {name}" for name in suggestions
            )

            return (
                "I couldn't identify one exact medicine. "
                "Please choose the complete product name:\n\n"
                + formatted
            )

        return (
            "I couldn't find that medicine in the "
            "local database. Please check its name."
        )

    # STEP 8: Generate answer from database
    # OpenRouter does NOT invent medicine facts.

    if intent == "compare":
        return compare_medicines(medicine, df)

    return medicine_information(medicine)
