# cspell:ignore smol genai
"""
smol_dev.py

Generates agent.py from main.prompt using Google Gemini.
Includes quota handling, code sanitization, and logging.
"""

import os
import re
import sys
import time
import logging
import google.generativeai as genai
from google.api_core import exceptions as google_api_exceptions
from dotenv import load_dotenv

# --- Constants ---
PROMPT_PATH = "main.prompt"
OUTPUT_DIR = "generated_agent"
OUTPUT_FILE = "agent.py"
# Updated MODEL_NAME to match the specification in main.prompt
MODEL_NAME = "gemini-2.0-flash"
LOG_FILE = "smol_dev.log"


def setup_api():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logging.critical(
            "%s", "Error: GOOGLE_API_KEY not found in environment variables."
        )
        sys.exit(1)

    genai.configure(api_key=api_key)
    logging.info("%s", "Google API Key configured successfully.")


def sanitize_python_code(response_text):
    if match := re.search(r"```python\s*(.*?)\s*```", response_text, re.DOTALL):
        return match.group(1).strip()
    else:
        logging.error(
            "%s",
            "Error: Could not find a ```python``` code block in the model response.",
        )
        return None


def load_prompt(file_path):
    if not os.path.exists(file_path):
        logging.error("Error: '%s' not found.", file_path)
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        prompt_text = f.read().strip()

    if not prompt_text:
        logging.error("Error: '%s' is empty.", file_path)
        sys.exit(1)

    return prompt_text


def generate_agent_code(prompt_text, model):
    """
    Calls Gemini API and retries if quota is exceeded.
    """
    for attempt in range(3):
        try:
            response = model.generate_content(prompt_text)
            code = sanitize_python_code(response.text)
            if code:
                return code
        except google_api_exceptions.GoogleAPIError as e:
            if "Quota exceeded" in str(e):
                logging.warning("Quota exceeded, retrying in 31 seconds...")
                time.sleep(31)
            else:
                raise
        except Exception as e:
            logging.error("Unexpected error during code generation: %s", e)
            raise

    logging.error("Failed to generate agent code due to quota limits.")
    sys.exit(1)


def save_agent_code(code, directory, filename):
    os.makedirs(directory, exist_ok=True)
    output_path = os.path.join(directory, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)

    logging.info("✅ Agent successfully generated at '%s'", output_path)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        filename=LOG_FILE,
        filemode="w",
    )

    try:
        setup_api()
        prompt_text = load_prompt(PROMPT_PATH)

        model = genai.GenerativeModel(MODEL_NAME)
        code = generate_agent_code(prompt_text, model)

        save_agent_code(code, OUTPUT_DIR, OUTPUT_FILE)

    except IOError as e:
        logging.error("File system error: %s", e)
        sys.exit(1)
    except google_api_exceptions.GoogleAPIError as e:
        logging.error("Google API Error: %s", e)
        sys.exit(1)
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
