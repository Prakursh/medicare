
import re


def expand_followup(question, last_medicine=None):
    """
    Resolve follow-up questions using the last
    successfully identified medicine.

    Only factual lookup questions are expanded.
    Medical safety questions remain unchanged.
    """

    if not last_medicine:
        return question

    q = re.sub(
        r"\s+", " ", question.lower().strip()
    ).rstrip("?.! ").strip()

    followups = {
        # Price
        "what is its price": (
            f"What is the price of {last_medicine}?"
        ),
        "what's its price": (
            f"What is the price of {last_medicine}?"
        ),
        "how much does it cost": (
            f"What is the price of {last_medicine}?"
        ),
        "and its price": (
            f"What is the price of {last_medicine}?"
        ),

        # Composition
        "what is its composition": (
            f"What is the composition of {last_medicine}?"
        ),
        "what's its composition": (
            f"What is the composition of {last_medicine}?"
        ),
        "what are its ingredients": (
            f"What are the ingredients in {last_medicine}?"
        ),
        "and its composition": (
            f"What is the composition of {last_medicine}?"
        ),

        # Manufacturer
        "who manufactures it": (
            f"Tell me about {last_medicine}"
        ),
        "who makes it": (
            f"Tell me about {last_medicine}"
        ),
        "what is its manufacturer": (
            f"Tell me about {last_medicine}"
        ),

        # Pack size
        "what is its pack size": (
            f"Tell me about {last_medicine}"
        ),
        "and its pack size": (
            f"Tell me about {last_medicine}"
        ),

        # Price comparisons
        "find cheaper alternatives": (
            f"Find cheaper composition matches for {last_medicine}"
        ),
        "are there cheaper alternatives": (
            f"Find cheaper composition matches for {last_medicine}"
        ),
        "compare its price": (
            f"Find cheaper composition matches for {last_medicine}"
        ),
        "any cheaper options": (
            f"Find cheaper composition matches for {last_medicine}"
        ),

        # General information
        "tell me about it": (
            f"Tell me about {last_medicine}"
        ),
    }

    return followups.get(q, question)
