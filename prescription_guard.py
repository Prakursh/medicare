
import re

MANDATED_PROMPT = (
    "This medication requires a valid prescription. "
    "Please consult your doctor."
)

# Starter rules for a restricted-drug demo.
# These are NOT a complete Indian Schedule H database.
# They must be validated against authoritative sources
# before clinical or commercial deployment.

RESTRICTED_INGREDIENTS = [
    "amoxicillin",
    "amoxycillin",
    "azithromycin",
    "alprazolam",
    "diazepam",
    "clonazepam",
]

RESTRICTED_BRANDS = [
    "augmentin",
    "moxikind-cv",
    "clavam",
]


def normalize(value):
    return re.sub(
        r"\s+", " ", str(value).lower()
    ).strip()


def contains_restricted_term(text):
    text = normalize(text)

    for term in (
        RESTRICTED_INGREDIENTS
        + RESTRICTED_BRANDS
    ):
        pattern = (
            r"(?<!\w)"
            + re.escape(term)
            + r"(?!\w)"
        )

        if re.search(pattern, text):
            return True

    return False


def check_query(question):
    """
    Check explicit restricted-drug mentions
    before the LLM is called.
    """
    if contains_restricted_term(question):
        return MANDATED_PROMPT

    return None


def check_medicine(medicine):
    """
    Check both product name and ingredients
    after database retrieval.
    """

    fields = [
        "name",
        "short_composition1",
        "short_composition2",
    ]

    combined = " ".join(
        str(medicine.get(field, ""))
        for field in fields
    )

    if contains_restricted_term(combined):
        return MANDATED_PROMPT

    return None
