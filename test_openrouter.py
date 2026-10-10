
import os
from dotenv import load_dotenv
from llm_parser import parse_question

load_dotenv()

key = os.getenv("OPENROUTER_API_KEY")

print("API key detected:", bool(key))
print("API key format valid:", bool(key and key.startswith("sk-or-")))
print("Model:", os.getenv("OPENROUTER_MODEL"))

if key:
    result = parse_question(
        "What is the price of Dolo 650 Tablet?"
    )
    print("OpenRouter result:", result)
else:
    print("ERROR: OpenRouter API key not loaded.")
