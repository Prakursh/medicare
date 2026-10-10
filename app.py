
from pathlib import Path
from datetime import datetime, timezone
import csv
import re

import pandas as pd
import streamlit as st

from medibot import get_response
from conversation import expand_followup
from prescription_guard import check_query, check_medicine


# ======================================
# 1. CONFIGURATION
# ======================================

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "indian_medicine_data.csv"

st.set_page_config(
    page_title="MediCare | MediBot",
    page_icon="💊",
    layout="wide",
)


# ======================================
# 2. LOAD AND PREPARE DATA
# ======================================

@st.cache_data(show_spinner="Loading medicine database...")
def load_data():
    df = pd.read_csv(DATA_PATH, low_memory=False).fillna("")

    df["name_search"] = (
        df["name"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    df["price_numeric"] = pd.to_numeric(
        df["price(₹)"]
        .astype(str)
        .str.replace(r"[₹,]", "", regex=True),
        errors="coerce",
    )

    def normalize_composition(row):
        ingredients = [
            str(row["short_composition1"]).strip().lower(),
            str(row["short_composition2"]).strip().lower(),
        ]

        ingredients = [
            ingredient
            for ingredient in ingredients
            if ingredient and ingredient != "nan"
        ]

        return "|".join(sorted(ingredients))

    df["composition_key"] = df.apply(
        normalize_composition,
        axis=1,
    )

    df["pack_key"] = (
        df["pack_size_label"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    df["discontinued"] = (
        df["Is_discontinued"]
        .astype(str)
        .str.lower()
        .str.strip()
        .isin(["true", "1", "yes"])
    )

    return df


try:
    df = load_data()
except Exception as exc:
    st.error(f"Could not load the medicine database: {exc}")
    st.stop()


# ======================================
# 3. HEADER AND DISCLAIMER
# ======================================

st.title("💊 MediCare")
st.subheader("Your Medicine Information Assistant")

st.info(
    "MediCare provides general medicine information using a "
    "local dataset. Listed prices may be outdated and are not "
    "live pharmacy quotes. Composition matches are not medical "
    "recommendations or proof that medicines are interchangeable."
)

if "acknowledged" not in st.session_state:
    st.session_state.acknowledged = False

acknowledged = st.checkbox(
    "I understand that MediCare does not replace professional "
    "medical advice, diagnosis, or prescriptions.",
    value=st.session_state.acknowledged,
)

st.session_state.acknowledged = acknowledged

if not acknowledged:
    st.warning("Please acknowledge the disclaimer to continue.")
    st.stop()


# ======================================
# 4. MEDICINE SEARCH
# ======================================

st.divider()
st.header("🔎 Search Medicines")

search_term = st.text_input(
    "Enter a medicine name",
    placeholder="Example: Dolo 650",
)

selected_medicine = None

if search_term.strip():

    query_warning = check_query(search_term)

    if query_warning:
        st.warning(query_warning)

    else:
        matches = df[
            df["name_search"].str.contains(
                re.escape(search_term.strip().lower()),
                regex=True,
                na=False,
            )
        ]

        if matches.empty:
            st.warning("No matching medicines found.")

        else:
            matches = matches.sort_values(
                by="name",
                key=lambda col: col.astype(str).str.lower(),
            )

            # Keep search results manageable.
            options = matches.head(100)

            selected_index = st.selectbox(
                "Select a medicine",
                options.index.tolist(),
                format_func=lambda idx: str(df.loc[idx, "name"]),
            )

            selected_medicine = df.loc[selected_index]

            medicine_warning = check_medicine(selected_medicine)

            if medicine_warning:
                st.warning(medicine_warning)
                selected_medicine = None

            else:
                st.subheader(str(selected_medicine["name"]))

                col1, col2 = st.columns(2)

                with col1:
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

                with col2:
                    st.write(
                        "**Pack size:**",
                        selected_medicine["pack_size_label"],
                    )

                    price = selected_medicine["price_numeric"]

                    if pd.notna(price):
                        st.metric("Listed price", f"₹{price:.2f}")
                    else:
                        st.write("**Listed price:** Not available")

                    if selected_medicine["discontinued"]:
                        st.warning(
                            "This medicine is marked as discontinued "
                            "in the dataset."
                        )


# ======================================
# 5. COMPOSITION AND PRICE COMPARISON
# ======================================

st.divider()
st.header("💰 Compare Composition-Matched Medicines")

st.caption(
    "Products are compared only when their recorded composition "
    "and pack-size labels match. This does not establish clinical "
    "equivalence or suitability for substitution."
)

if selected_medicine is not None:

    composition = selected_medicine["composition_key"]
    pack_size = selected_medicine["pack_key"]
    current_price = selected_medicine["price_numeric"]

    if not composition or not pack_size:
        st.info(
            "Insufficient composition or pack-size information "
            "for comparison."
        )

    else:
        alternatives = df[
            (df["composition_key"] == composition)
            & (df["pack_key"] == pack_size)
            & (~df["discontinued"])
            & (df["price_numeric"] > 0)
            & (df.index != selected_medicine.name)
        ].copy()

        # Exclude products caught by the prescription guard.
        if not alternatives.empty:
            alternatives = alternatives[
                ~alternatives.apply(
                    lambda row: bool(check_medicine(row)),
                    axis=1,
                )
            ]

        alternatives = alternatives.sort_values(
            by="price_numeric"
        ).head(10)

        if alternatives.empty:
            st.info(
                "No additional composition-and-pack matches "
                "were found in the dataset."
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

            if pd.notna(current_price) and current_price > 0:
                cheaper = alternatives[
                    alternatives["price_numeric"] < current_price
                ]

                if not cheaper.empty:
                    lowest_price = cheaper[
                        "price_numeric"
                    ].min()

                    saving = current_price - lowest_price

                    percentage = (
                        saving / current_price
                    ) * 100

                    st.success(
                        f"Lowest matching listed price: "
                        f"₹{lowest_price:.2f}. "
                        f"Difference: ₹{saving:.2f} "
                        f"({percentage:.1f}%)."
                    )

            st.warning(
                "Do not switch medicines based on this comparison. "
                "Consult a pharmacist or doctor to confirm whether "
                "a product is appropriate."
            )

else:
    st.info("Search for and select a medicine to compare products.")


# ======================================



def answer_followup(question, last_medicine, df):
    """Answer factual follow-ups without repeating the full record."""

    if not last_medicine:
        return None

    q = " ".join(
        question.lower().strip().rstrip("?.! ").split()
    )

    price_questions = {
        "what's its price",
        "what is its price",
        "how much does it cost",
        "and its price",
    }

    composition_questions = {
        "what is its composition",
        "what's its composition",
        "what are its ingredients",
        "and its composition",
        "and its ingredients",
    }

    manufacturer_questions = {
        "who manufactures it",
        "who makes it",
        "what is its manufacturer",
        "what's its manufacturer",
        "and its manufacturer",
    }

    pack_questions = {
        "what is its pack size",
        "what's its pack size",
        "and its pack size",
    }

    if q in price_questions:
        intent = "price"
    elif q in composition_questions:
        intent = "composition"
    elif q in manufacturer_questions:
        intent = "manufacturer"
    elif q in pack_questions:
        intent = "pack"
    else:
        return None

    matches = df[
        df["name_search"] == last_medicine.lower().strip()
    ]

    if len(matches) != 1:
        return None

    medicine = matches.iloc[0]

    # Apply prescription checks before showing any details.
    restriction = (
        check_query(question)
        or check_query(last_medicine)
        or check_medicine(medicine)
    )

    if restriction:
        return restriction

    name = str(medicine["name"])

    if intent == "price":
        price = medicine["price_numeric"]

        if pd.isna(price):
            return f"No listed price is available for {name}."

        return (
            f"**{name}** has a dataset-listed price of "
            f"**₹{price:.2f}**."
        )

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
            return f"No composition information is available for {name}."

        return (
            f"**{name}** contains "
            f"**{', '.join(ingredients)}**."
        )

    if intent == "manufacturer":
        manufacturer = str(
            medicine["manufacturer_name"]
        ).strip()

        if not manufacturer:
            return f"No manufacturer information is available for {name}."

        return f"**{manufacturer}** manufactures {name}."

    if intent == "pack":
        pack = str(medicine["pack_size_label"]).strip()

        if not pack:
            return f"No pack-size information is available for {name}."

        return f"**{name}** comes in **{pack}**."

    return None


# 6. MEDIBOT CHAT
# ======================================

st.divider()
st.header("🤖 MediBot")

st.write(
    "Ask about medicine composition, manufacturers, "
    "pack sizes, or listed prices."
)

if "medibot_messages" not in st.session_state:
    st.session_state.medibot_messages = []

if "last_medicine" not in st.session_state:
    st.session_state.last_medicine = None


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

            # Resolve follow-up questions such as
            # "What's its price?"
            expanded = expand_followup(
                question,
                st.session_state.last_medicine,
            )

            # Enforce the prescription guard before
            # sending the query to the chatbot.
            restriction_message = (
                check_query(question)
                or check_query(expanded)
            )

            if restriction_message:
                response = restriction_message

            else:
                try:
                    
                    # Try answering the follow-up directly from the dataset.
                    response = answer_followup(
                            question,
                            st.session_state.last_medicine,
                            df
)

                    # Use the normal MediBot pipeline for other questions.
                    if response is None:
                        response = get_response(expanded, df)


                except Exception:
                    response = (
                        "MediBot could not process your request "
                        "right now. Please try again."
                    )

            # Update conversation memory when a
            # medicine information response is found.
            if response.startswith("### "):

                first_line = response.splitlines()[0]

                if not first_line.startswith(
                    "### Composition matches for "
                ):

                    returned_name = first_line[4:].strip()

                    found = df[
                        df["name_search"]
                        == returned_name.lower()
                    ]

                    if len(found) == 1:

                        record = found.iloc[0]

                        if not check_medicine(record):
                            st.session_state.last_medicine = (
                                str(record["name"])
                            )

        st.markdown(response)

    st.session_state.medibot_messages.append(
        {
            "role": "assistant",
            "content": response,
        }
    )


# ======================================

# ======================================
# 7. USER SATISFACTION FEEDBACK
# ======================================

with st.sidebar:
    with st.expander("⭐ Rate MediCare", expanded=False):

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
                st.info("Feedback already submitted.")

            elif rating is None:
                st.warning("Please select a rating.")

            else:
                import csv
                from datetime import datetime, timezone

                feedback_path = BASE_DIR / "feedback.csv"
                file_exists = feedback_path.exists()

                with open(
                    feedback_path,
                    "a",
                    newline="",
                    encoding="utf-8",
                ) as file:

                    writer = csv.writer(file)

                    if not file_exists:
                        writer.writerow([
                            "timestamp",
                            "rating",
                            "comment",
                        ])

                    writer.writerow([
                        datetime.now(timezone.utc).isoformat(),
                        rating + 1,
                        comment,
                    ])

                st.session_state.feedback_submitted = True
                st.success("Thanks for your feedback!")

# 8. FOOTER
# ======================================

st.divider()

st.caption(
    "MediCare | Educational pharmacy information assistant. "
    "Not a substitute for professional medical advice."
)

st.caption(
    "Prescription screening is based on a limited ruleset "
    "and must not be treated as a complete regulatory check. "
    "Medicine prices are dataset values, not live pharmacy prices."
)
