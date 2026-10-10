
# 💊 MediCare — AI-Powered Pharmacy Information Assistant

MediCare is a conversational pharmacy information assistant built with Python, Streamlit, and OpenRouter.

It helps users search a local database of Indian medicines, compare recorded prices, discover products with matching composition and pack-size information, and ask follow-up questions through MediBot.

The application emphasizes responsible handling of medical queries through prescription screening, restrictions on personalized medical advice, and transparent data limitations.

## Features

### 1. Medicine Search

- Search medicines by brand or product name.
- View manufacturer, active composition, pack size, and listed price.
- Identify medicines marked as discontinued in the dataset.
- Retrieve information from a local database containing approximately 254,000 records.

### 2. Composition-Based Price Comparison

- Find medicines with matching recorded composition and pack-size labels.
- Compare their dataset-listed prices.
- Identify lower-priced composition matches.
- Exclude discontinued records and products detected by the prescription guard.
- Display warnings that composition matching does not guarantee clinical interchangeability.

Prices are historical dataset values, **not live quotes from pharmacies**.

### 3. MediBot — Conversational Assistant

MediBot supports natural-language questions about medicine information.

Example conversation:

**User:** What is Dolo 650 Tablet?

**MediBot:** Dolo 650 Tablet contains Paracetamol (650mg), is manufactured by Micro Labs Ltd, and has a dataset-listed price of ₹34.27.

**User:** What's its price?

**MediBot:** Dolo 650 Tablet has a dataset-listed price of ₹34.27.

**User:** What is its composition?

**MediBot:** Dolo 650 Tablet contains Paracetamol (650mg).

**User:** Find cheaper alternatives.

**MediBot:** Returns available composition-and-pack matches from the dataset, accompanied by appropriate safety warnings.

MediBot remembers the last identified medicine during the current chat session. Common factual follow-ups are answered directly from the dataset, avoiding unnecessary repetition and additional API calls.

### 4. Medical Safety and Prescription Screening

MediCare includes rule-based safety checks designed to:

- Detect a limited set of restricted medicine names and ingredients.
- Display the required prescription warning for recognized restricted products.
- Avoid personalized dosage recommendations, diagnosis, and treatment decisions.
- Respond cautiously to emergency or potentially unsafe medical requests.
- Check both user queries and relevant medicine records.

For detected restricted medicines, the application displays:

> This medication requires a valid prescription. Please consult your doctor.

**Important:** The current prescription screening is a prototype based on a limited ruleset. It is not a complete or authoritative implementation of India's Schedule H regulations.

### 5. User Feedback

- Optional five-star experience rating.
- Collapsed feedback panel in the Streamlit sidebar.
- Optional written comments.
- Local feedback storage in `feedback.csv`.

Feedback is collected for evaluation and improvement. No satisfaction score is claimed without sufficient actual user ratings.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python 3.12 |
| User interface | Streamlit |
| Data processing | pandas |
| Language-model access | OpenRouter API |
| Configured LLM | GPT-4o mini |
| Conversation memory | Streamlit session state |
| Medicine lookup | Local CSV dataset |
| Prescription screening | Rule-based Python checks |
| Automated testing | Python unittest |
| Configuration | python-dotenv |

## System Architecture

1. **Streamlit interface:** Accepts medicine searches and chat messages.
2. **Safety layer:** Checks for restricted products and unsafe medical requests.
3. **Conversation layer:** Uses session context to resolve supported follow-up questions.
4. **Query parser:** Uses OpenRouter to interpret natural-language requests when necessary.
5. **Medicine retrieval:** Looks up relevant records in the local dataset.
6. **Comparison engine:** Finds composition-and-pack matches and compares listed prices.
7. **Response generation:** Displays grounded medicine information and relevant safety warnings.

The LLM is used primarily to interpret questions. Medicine-specific factual answers are retrieved from the dataset rather than invented by the model.

## Project Structure

- `app.py` — Main Streamlit application and user interface.
- `medibot.py` — Medicine retrieval, response generation, comparisons, and safety logic.
- `llm_parser.py` — OpenRouter-based natural-language query parsing.
- `conversation.py` — Follow-up question handling.
- `prescription_guard.py` — Restricted-medicine screening.
- `test_medibot.py` — MediBot and safety tests.
- `test_prescription.py` — Prescription-screening tests.
- `test_conversation.py` — Conversation-memory tests.
- `requirements.txt` — Python dependencies.
- `data/indian_medicine_data.csv` — Local medicine dataset.
- `.env` — Local API configuration, excluded from version control.

## Installation and Setup

**1. Clone the repository**

```bash
git clone https://github.com/Prakursh/medicare.git
cd medicare
```

**2. Create a virtual environment**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**3. Install dependencies**

```powershell
python -m pip install -r requirements.txt
```

**4. Configure OpenRouter**

Create a `.env` file in the project root containing:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=openai/gpt-4o-mini
```

Never commit your real API key to GitHub.

**5. Prepare the dataset**

Ensure the medicine CSV file is available at:

`data/indian_medicine_data.csv`

The application expects columns including `name`, `manufacturer_name`, `short_composition1`, `short_composition2`, `pack_size_label`, `price(₹)`, and `Is_discontinued`.

**6. Start the application**

```powershell
python -m streamlit run app.py
```

Open the local URL displayed in the terminal.

## Testing

The project includes automated tests covering:

- Medical safety classifications.
- Personal medical advice restrictions.
- Prescription screening.
- Medicine lookup and response generation.
- Follow-up question expansion.
- Handling of selected LLM and API failure scenarios.
- Restricted-product filtering in composition comparisons.

Run the test suite:

```powershell
python -m unittest -v test_medibot.py test_prescription.py test_conversation.py
```

The updated suite contains **19 tests**. Passing these tests does not establish comprehensive medical or regulatory safety.

Additional manual testing covered multi-turn medicine information retrieval, targeted follow-up answers, composition-based comparisons, and safety responses.

## Current Limitations

**Live pharmacy integration:** The application does not currently retrieve real-time price, availability, delivery, or seller information from certified e-pharmacies.

**Prescription coverage:** Restricted-medicine detection uses a limited list of terms and cannot reliably identify every prescription-only product.

**Clinical equivalence:** Products matching recorded ingredients and pack-size labels are not necessarily interchangeable. Additional clinical factors require professional verification.

**Dataset quality:** Product prices, availability, and discontinued status may be outdated or incomplete.

**Conversation memory:** MediBot stores limited session-level context rather than a complete medical conversation history.

**Medical advice:** MediCare does not diagnose conditions, prescribe medicines, or determine whether a treatment is suitable for an individual.

## Potential Improvements

- Integrate verified pharmacy data sources for live price and availability comparisons.
- Expand prescription screening using authoritative regulatory information.
- Improve strength, dosage-form, and formulation normalization.
- Add broader conversational context handling.
- Evaluate retrieval accuracy, response quality, and user satisfaction on larger test sets.
- Improve accessibility and mobile usability.

## Disclaimer

MediCare is an educational prototype. Its information should not be used as a substitute for medical advice, diagnosis, prescriptions, or professional medication review.

Users should consult qualified healthcare professionals before starting, stopping, or substituting medicines.
