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
MODEL_NAME = "gemini-2.0-flash"
LOG_FILE = "smol_dev.log"


def setup_logging():
    """Configure both file and console logging."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # File handler
    fh = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)


def setup_api():
    """Load environment and configure Gemini API."""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logging.critical("Error: GOOGLE_API_KEY not found in environment variables.")
        sys.exit(1)

    genai.configure(api_key=api_key)
    logging.info("Google API Key configured successfully.")


def sanitize_python_code(response_text):
    """
    Extracts valid Python code from the Gemini response.
    Handles both fenced (```python ... ```) and raw code outputs.
    """
    if not response_text:
        logging.error("Empty response received from the model.")
        return None

    # Prefer fenced code block
    match = re.search(r"```python\s*(.*?)\s*```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try generic fenced code
    match = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Otherwise, assume the whole thing is code
    logging.warning("No markdown fences detected. Using raw text as code.")
    return response_text.strip()


def load_prompt(file_path):
    """Loads the main.prompt file."""
    if not os.path.exists(file_path):
        logging.error("Error: '%s' not found.", file_path)
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        prompt_text = f.read().strip()

    if not prompt_text:
        logging.error("Error: '%s' is empty.", file_path)
        sys.exit(1)

    logging.info("Prompt loaded successfully.")
    return prompt_text


def generate_agent_code(prompt_text, model):
    """Calls Gemini API and retries if quota or transient errors occur."""
    for attempt in range(3):
        try:
            logging.info("Generating agent code (attempt %d)...", attempt + 1)
            response = model.generate_content(prompt_text)
            response_text = getattr(response, "text", None)

            code = sanitize_python_code(response_text)
            if code:
                return code

        except google_api_exceptions.ResourceExhausted:
            logging.warning("Quota or rate limit hit. Retrying in 30 seconds...")
            time.sleep(30)

        except google_api_exceptions.GoogleAPIError as e:
            logging.error("Google API Error: %s", e)
            time.sleep(10)

        except Exception as e:
            logging.error("Unexpected error during code generation: %s", e)
            time.sleep(5)

    logging.critical("Failed to generate agent code after multiple attempts.")
    sys.exit(1)


def save_agent_code(code, directory, filename):
    """Saves the generated Python agent to a file."""
    os.makedirs(directory, exist_ok=True)
    output_path = os.path.join(directory, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)

    logging.info("✅ Agent successfully generated at '%s'", output_path)


def main():
    setup_logging()
    logging.info("🚀 Starting Smol Developer...")

    try:
        setup_api()
        prompt_text = load_prompt(PROMPT_PATH)

        model = genai.GenerativeModel(MODEL_NAME)
        code = generate_agent_code(prompt_text, model)

        save_agent_code(code, OUTPUT_DIR, OUTPUT_FILE)
        logging.info("🎉 Smol Developer finished successfully!")

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
