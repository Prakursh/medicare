
from pathlib import Path
from datetime import datetime, timezone
import csv
import re

import pandas as pd
import streamlit as st

from medibot import get_response, compare_medicines, safety_check
from prescription_guard import check_query, check_medicine


# ======================================
# 1. CONFIGURATION AND DATA
# ======================================

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "indian_medicine_data.csv"

st.set_page_config(
    page_title="MediCare | MediBot",
    page_icon="💊",
    layout="wide",
)


@st.cache_data(show_spinner="Loading medicine database...")
def load_data():
    data = pd.read_csv(
        DATA_PATH,
        low_memory=False,
    ).fillna("")

    data["name_search"] = (
        data["name"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    data["price_numeric"] = pd.to_numeric(
        data["price(₹)"]
        .astype(str)
        .str.replace(r"[₹,]", "", regex=True),
        errors="coerce",
    )

    def composition_key(row):
        parts = [
            str(row[column]).strip().lower()
            for column in (
                "short_composition1",
                "short_composition2",
            )
        ]

        return "|".join(
            sorted(
                x for x in parts
                if x and x != "nan"
            )
        )

    data["composition_key"] = data.apply(
        composition_key,
        axis=1,
    )

    data["pack_key"] = (
        data["pack_size_label"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    data["discontinued"] = (
        data["Is_discontinued"]
        .astype(str)
        .str.lower()
        .str.strip()
        .isin(["true", "1", "yes"])
    )

    return data


# ======================================
# 2. NATURAL FOLLOW-UP DETECTION
# ======================================

def followup_intent(question):
    """
    Identify short contextual questions without
    needing another OpenRouter API call.
    """

    q = str(question).lower().replace("’", "'")

    q = re.sub(r"[?.!,]+", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"\s+please$", "", q).strip()

    patterns = {
        "cheaper": [
            r"(?:are there|is there|do you have|"
            r"can you (?:find|show)|"
            r"could you (?:find|show)|"
            r"find|show(?: me)?|list|give me|"
            r"suggest|what about|and)?\s*"
            r"(?:any\s+)?"
            r"(?:cheaper|less expensive|lower priced|"
            r"lower cost)\s+"
            r"(?:alternatives?|options?|products?|"
            r"brands?|medicines?|matches?|ones?)"
            r"(?:\s+(?:for|to|than)\s+"
            r"(?:it|this|that|this medicine))?",

            r"(?:are there|is there|any|find|"
            r"show me|what about)?\s*"
            r"(?:any\s+)?"
            r"(?:alternatives?|other options)"
            r"(?:\s+(?:for|to)\s+"
            r"(?:it|this|that|this medicine))?",

            r"(?:anything|something)\s+cheaper",

            r"is there a cheaper "
            r"(?:one|option|alternative)",
        ],

        "compare": [
            r"compare(?:\s+(?:its|the))?\s+prices?",
            r"compare\s+(?:it|this medicine)"
            r"(?:\s+with others)?",
            r"price comparison",
        ],

        "price": [
            r"(?:(?:what is|what's|what are|"
            r"tell me|show me|and|what about)\s+)?"
            r"(?:(?:the|its)\s+)?"
            r"(?:price|prices|pricing|cost)"
            r"(?:\s+of\s+(?:it|this|that))?",

            r"how much(?:\s+is it|"
            r"\s+does it cost)?",

            r"what does it cost",
            r"how expensive is it",
        ],

        "composition": [
            r"(?:(?:what is|what's|tell me|"
            r"show me|and|what about)\s+)?"
            r"(?:(?:the|its)\s+)?"
            r"(?:composition|ingredients?)",

            r"what (?:are|is) (?:its|the) "
            r"(?:composition|ingredients?)",

            r"what does it contain",
        ],

        "manufacturer": [
            r"(?:(?:what is|what's|tell me|"
            r"and|what about)\s+)?"
            r"(?:(?:the|its)\s+)?manufacturer",

            r"who (?:makes|manufactures) it",

            r"who is it made by",
        ],

        "pack": [
            r"(?:(?:what is|what's|tell me|"
            r"and|what about)\s+)?"
            r"(?:(?:the|its)\s+)?"
            r"(?:pack|pack size|packaging)",

            r"how many tablets "
            r"(?:are )?in (?:a|the) pack",
        ],

        "information": [
            r"(?:tell me about|what about|describe) "
            r"(?:it|this medicine)",
        ],
    }

    for intent, expressions in patterns.items():
        if any(
            re.fullmatch(expr, q)
            for expr in expressions
        ):
            return intent

    return None


# ======================================
# 3. CONVERSATION MEMORY
# ======================================

def get_context_record(last_medicine, data):
    """
    Retrieve the medicine currently remembered
    by MediBot.
    """

    if not last_medicine:
        return None

    matching = data[
        data["name_search"]
        == last_medicine.lower().strip()
    ]

    if len(matching) == 1:
        return matching.iloc[0]

    return None


# ======================================
# 4. CHEAPER MEDICINE COMPARISON
# ======================================

def cheaper_matches(medicine, data):
    """
    Find lower-priced records with the same
    recorded composition and pack-size label.

    These are not verified clinical substitutes.
    """

    if medicine["discontinued"]:
        return (
            "This product is marked discontinued "
            "in the dataset."
        )

    composition = str(medicine["composition_key"])
    pack = str(medicine["pack_key"])
    price = medicine["price_numeric"]

    if (
        not composition
        or not pack
        or pd.isna(price)
        or price <= 0
    ):
        return (
            "There is insufficient price, composition, "
            "or pack information to compare."
        )

    candidates = data[
        (data["composition_key"] == composition)
        & (data["pack_key"] == pack)
        & (~data["discontinued"])
        & (data["price_numeric"] > 0)
        & (data["price_numeric"] < price)
        & (data["name"] != medicine["name"])
    ].copy()

    # Exclude medicines recognized by the
    # prescription guard.
    if not candidates.empty:
        candidates = candidates.loc[
            ~candidates.apply(
                lambda row: bool(check_medicine(row)),
                axis=1,
            )
        ]

    if candidates.empty:
        return (
            f"No lower-priced composition-and-pack matches "
            f"for **{medicine['name']}** were found "
            f"in this dataset."
        )

    candidates = candidates.sort_values(
        "price_numeric"
    ).head(5)

    lines = [
        f"### Lower-priced composition matches "
        f"for {medicine['name']}",
        "",
        f"Current listed price: **₹{price:.2f}**.",
        "",
    ]

    for _, row in candidates.iterrows():
        listed = row["price_numeric"]

        saving_pct = (
            (price - listed) / price
        ) * 100

        lines.append(
            f"- **{row['name']}** — "
            f"₹{listed:.2f} "
            f"({saving_pct:.1f}% lower listed price; "
            f"{row['manufacturer_name']})"
        )

    lines += [
        "",
        "⚠️ These are **unverified composition-and-pack "
        "matches**, not confirmed interchangeable medicines. "
        "Do not substitute products without a pharmacist "
        "or clinician checking their formulation and "
        "suitability. Prices are dataset values, not "
        "live pharmacy offers.",
    ]

    return "\n".join(lines)


# ======================================
# 5. ANSWER CONTEXTUAL QUESTIONS
# ======================================

def answer_followup(question, last_medicine, data):
    """
    Answer recognized follow-up questions directly
    from the local medicine dataset.
    """

    intent = followup_intent(question)

    if intent is None or not last_medicine:
        return None

    medicine = get_context_record(
        last_medicine,
        data,
    )

    if medicine is None:
        return None

    # Prescription checks also apply to follow-ups.
    restriction = (
        check_query(question)
        or check_query(last_medicine)
        or check_medicine(medicine)
    )

    if restriction:
        return restriction

    name = str(medicine["name"])

    # Cheaper alternatives
    if intent == "cheaper":
        return cheaper_matches(medicine, data)

    # General price comparison
    if intent == "compare":
        return compare_medicines(medicine, data)

    # Price
    if intent == "price":
        price = medicine["price_numeric"]

        if pd.isna(price):
            return (
                f"No listed price is available for {name}."
            )

        return (
            f"**{name}** has a dataset-listed price "
            f"of **₹{price:.2f}**."
        )

    # Composition
    if intent == "composition":
        ingredients = [
            str(medicine[column]).strip()
            for column in (
                "short_composition1",
                "short_composition2",
            )
            if str(medicine[column]).strip()
        ]

        if not ingredients:
            return (
                f"Composition information for "
                f"{name} is unavailable."
            )

        return (
            f"**{name}** contains "
            f"**{', '.join(ingredients)}**."
        )

    # Manufacturer
    if intent == "manufacturer":
        maker = str(
            medicine["manufacturer_name"]
        ).strip()

        if not maker:
            return (
                f"Manufacturer information for "
                f"{name} is unavailable."
            )

        return f"**{maker}** manufactures {name}."

    # Pack size
    if intent == "pack":
        pack = str(
            medicine["pack_size_label"]
        ).strip()

        if not pack:
            return (
                f"Pack-size information for "
                f"{name} is unavailable."
            )

        return f"**{name}** comes in **{pack}**."

    # General information
    if intent == "information":
        from medibot import medicine_information

        return medicine_information(medicine)

    return None


# ======================================
# 6. LOAD DATABASE
# ======================================

try:
    df = load_data()

except Exception as exc:
    st.error(
        f"Could not load the medicine database: {exc}"
    )
    st.stop()


# ======================================
# 7. HEADER AND DISCLAIMER
# ======================================

st.title("💊 MediCare")
st.subheader("Your Medicine Information Assistant")

st.info(
    "MediCare uses a local dataset. Listed prices may "
    "be outdated and are not live pharmacy quotes. "
    "Composition matches do not establish clinical "
    "interchangeability or suitability."
)

acknowledged = st.checkbox(
    "I understand that MediCare does not replace "
    "medical advice, diagnosis, or prescriptions.",
    key="acknowledged",
)

if not acknowledged:
    st.warning(
        "Please acknowledge the disclaimer to continue."
    )
    st.stop()


# ======================================
# 8. MEDICINE SEARCH
# ======================================

st.divider()
st.header("🔎 Search Medicines")

search_term = st.text_input(
    "Enter a medicine name",
    placeholder="Example: Dolo 650",
)

selected_medicine = None

if search_term.strip():

    restriction = check_query(search_term)

    if restriction:
        st.warning(restriction)

    else:
        matches = df[
            df["name_search"].str.contains(
                search_term.strip().lower(),
                regex=False,
                na=False,
            )
        ].sort_values(
            "name",
            key=lambda col: col.astype(str).str.lower(),
        )

        if matches.empty:
            st.warning("No matching medicines found.")

        else:
            options = matches.head(100)

            selected_index = st.selectbox(
                "Select a medicine",
                options.index.tolist(),
                format_func=lambda idx: str(
                    df.loc[idx, "name"]
                ),
            )

            selected_medicine = df.loc[selected_index]

            restriction = check_medicine(
                selected_medicine
            )

            if restriction:
                st.warning(restriction)
                selected_medicine = None

            else:
                st.subheader(
                    str(selected_medicine["name"])
                )

                left, right = st.columns(2)

                with left:
                    st.write(
                        "**Manufacturer:**",
                        selected_medicine["manufacturer_name"],
                    )

                    st.write(
                        "**Composition 1:**",
                        selected_medicine["short_composition1"],
                    )

                    st.write(
                        "**Composition 2:**",
                        selected_medicine["short_composition2"],
                    )

                with right:
                    st.write(
                        "**Pack size:**",
                        selected_medicine["pack_size_label"],
                    )

                    price = selected_medicine[
                        "price_numeric"
                    ]

                    if pd.notna(price):
                        st.metric(
                            "Listed price",
                            f"₹{price:.2f}",
                        )
                    else:
                        st.write(
                            "**Listed price:** Not available"
                        )

                    if selected_medicine["discontinued"]:
                        st.warning(
                            "Marked discontinued in the dataset."
                        )


# ======================================
# 9. COMPOSITION AND PRICE COMPARISON
# ======================================

st.divider()
st.header("💰 Compare Composition-Matched Medicines")

st.caption(
    "Products are matched by their recorded ingredients "
    "and pack-size labels. A matching record is not "
    "a clinically verified substitute."
)

if selected_medicine is None:
    st.info(
        "Search for and select a medicine "
        "to compare products."
    )

else:
    composition = selected_medicine[
        "composition_key"
    ]

    pack = selected_medicine["pack_key"]

    price = selected_medicine["price_numeric"]

    if (
        not composition
        or not pack
        or selected_medicine["discontinued"]
    ):
        st.info(
            "Insufficient data or discontinued product; "
            "comparison unavailable."
        )

    else:
        alternatives = df[
            (df["composition_key"] == composition)
            & (df["pack_key"] == pack)
            & (~df["discontinued"])
            & (df["price_numeric"] > 0)
            & (df.index != selected_medicine.name)
        ].copy()

        if not alternatives.empty:
            alternatives = alternatives.loc[
                ~alternatives.apply(
                    lambda row: bool(check_medicine(row)),
                    axis=1,
                )
            ]

        alternatives = alternatives.sort_values(
            "price_numeric"
        ).head(10)

        if alternatives.empty:
            st.info(
                "No other eligible composition-and-pack "
                "matches found."
            )

        else:
            comparison = alternatives[
                [
                    "name",
                    "manufacturer_name",
                    "pack_size_label",
                    "price_numeric",
                ]
            ].copy()

            comparison.columns = [
                "Medicine",
                "Manufacturer",
                "Pack size",
                "Listed price (₹)",
            ]

            st.dataframe(
                comparison,
                use_container_width=True,
                hide_index=True,
            )

            if pd.notna(price) and price > 0:
                cheaper = alternatives[
                    alternatives["price_numeric"] < price
                ]

                if not cheaper.empty:
                    lowest = cheaper[
                        "price_numeric"
                    ].min()

                    difference = price - lowest

                    st.success(
                        f"Lowest matching listed price: "
                        f"₹{lowest:.2f}. "
                        f"Difference: ₹{difference:.2f} "
                        f"({difference / price * 100:.1f}%)."
                    )

            st.warning(
                "Do not change medicines based on this "
                "table. A pharmacist or doctor must check "
                "suitability, strength, dosage form, "
                "and formulation."
            )


# ======================================
# 10. MEDIBOT CHAT
# ======================================

st.divider()
st.header("🤖 MediBot")

st.write(
    "Ask about composition, manufacturer, pack size, "
    "listed prices, or lower-priced matches."
)

if "medibot_messages" not in st.session_state:
    st.session_state.medibot_messages = []

if "last_medicine" not in st.session_state:
    st.session_state.last_medicine = None

# Display existing conversation
for message in st.session_state.medibot_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask MediBot...")

if question:

    st.session_state.medibot_messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):

        with st.spinner("Checking your question..."):

            try:
                # First check restricted medicine names.
                restriction = check_query(question)

                if restriction:
                    st.session_state.last_medicine = None
                    response = restriction

                else:
                    # Medical safety applies BEFORE
                    # direct follow-ups and OpenRouter.
                    safety = safety_check(question)

                    if safety:
                        response = safety

                    else:
                        # Handle recognized follow-ups
                        # from the remembered medicine.
                        response = answer_followup(
                            question,
                            st.session_state.last_medicine,
                            df,
                        )

                        if response is None:
                            # New medicine questions go
                            # through the existing MediBot.
                            response = get_response(
                                question,
                                df,
                            )

                # Remember a successfully retrieved
                # medicine for future questions.
                if (
                    response.startswith("### ")
                    and not response.startswith(
                        (
                            "### Composition matches for ",
                            "### Lower-priced composition matches for ",
                        )
                    )
                ):
                    returned_name = (
                        response.splitlines()[0][4:].strip()
                    )

                    record = get_context_record(
                        returned_name,
                        df,
                    )

                    if (
                        record is not None
                        and not check_medicine(record)
                    ):
                        st.session_state.last_medicine = (
                            str(record["name"])
                        )

            except Exception:
                response = (
                    "MediBot could not process this request "
                    "right now. Please try again."
                )

        st.markdown(response)

    st.session_state.medibot_messages.append(
        {
            "role": "assistant",
            "content": response,
        }
    )


# ======================================
# 11. USER FEEDBACK
# ======================================

with st.sidebar:

    with st.expander(
        "⭐ Rate MediCare",
        expanded=False,
    ):

        st.write("How helpful was MediCare?")

        rating = st.feedback(
            "stars",
            key="feedback_stars",
        )

        comment = st.text_area(
            "Additional feedback (optional)",
            max_chars=500,
            key="feedback_comment",
        )

        if "feedback_submitted" not in st.session_state:
            st.session_state.feedback_submitted = False

        if st.button("Submit Feedback"):

            if st.session_state.feedback_submitted:
                st.info(
                    "Feedback already submitted "
                    "for this session."
                )

            elif rating is None:
                st.warning("Please select a rating.")

            else:
                feedback_path = (
                    BASE_DIR / "feedback.csv"
                )

                file_exists = feedback_path.exists()

                with open(
                    feedback_path,
                    "a",
                    newline="",
                    encoding="utf-8",
                ) as file:

                    writer = csv.writer(file)

                    if not file_exists:
                        writer.writerow(
                            [
                                "timestamp",
                                "rating",
                                "comment",
                            ]
                        )

                    writer.writerow(
                        [
                            datetime.now(
                                timezone.utc
                            ).isoformat(),
                            rating + 1,
                            comment,
                        ]
                    )

                st.session_state.feedback_submitted = True

                st.success(
                    "Thank you! Your feedback was recorded."
                )


# ======================================
# 12. FOOTER
# ======================================

st.divider()

st.caption(
    "MediCare is educational and does not replace "
    "medical advice or prescriptions."
)

st.caption(
    "Prescription screening is limited; prices are "
    "dataset values, not live pharmacy quotes; "
    "composition matches are not verified "
    "interchangeable products."
)
