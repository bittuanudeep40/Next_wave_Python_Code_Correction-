import os
import sys
import re
import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions as google_api_exceptions
from dotenv import load_dotenv

# --- 1. Configuration and Setup ---

# Set page config
st.set_page_config(
    page_title="AI Python Code Corrector",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Function to configure the Gemini API
def setup_api():
    """
    Load API key from .env or Streamlit secrets and configure Gemini.
    Returns True on success, False on failure.
    """
    try:
        # Try loading from .env (for local development)
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")

        # If not in .env, try Streamlit secrets (for deployment)
        if not api_key:
            if "GOOGLE_API_KEY" in st.secrets:
                api_key = st.secrets["GOOGLE_API_KEY"]

        # If still no key, show an error
        if not api_key:
            st.error("Error: GOOGLE_API_KEY not found. Please set it in your .env file or Streamlit secrets.")
            return False

        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        st.error(f"Error configuring Generative AI: {e}")
        return False

def sanitize_response(text: str) -> str:
    """
    Cleans the AI's response, removing markdown fences.
    This is a Python port of the JavaScript sanitizeResponse function.
    """
    if not text:
        return ""
    # Regex to find content within ```python ... ```
    match = re.search(r"```python\s*([\s\S]*?)\s*```", text, re.DOTALL)
    if match and match.group(1):
        return match.group(1).strip()
    # Fallback: remove any triple backticks
    return text.replace("```", "").strip()

# --- 2. The Streamlit UI ---

# Header
st.title("🤖 AI Python Code Corrector")
st.write(
    "Paste your broken Python code below. The AI will analyze it and provide a fix."
)

# Text Area for user input
input_code = st.text_area(
    "Broken Python Code",
    height=300,
    placeholder="def my_function(a, b)\n    return a - b\n\n# Test\nprint(my_function(5, 3) == 8) # This will fail"
)

# "Fix My Code" button
if st.button("⚡ Fix My Code", use_container_width=True):
    if not input_code.strip():
        st.error("Please paste your Python code into the box first.")
    else:
        # --- 3. Run the AI Logic (when button is clicked) ---
        if setup_api(): # Only proceed if API is configured
            try:
                # The system prompt is taken directly from your index.html
                system_prompt = """You are an expert Python developer and code reviewer.
Your task is to analyze the provided Python code, identify any bugs, errors, or logical issues, and provide the complete, corrected code.
Your response must contain ONLY the raw, corrected Python code.
Do not include explanations, apologies, markdown formatting (like ```python), or any text other than the code itself."""

                # Show a spinner while the AI is working
                with st.spinner("AI is thinking..."):
                    # Create the model with the system prompt
                    model = genai.GenerativeModel(
                        "gemini-2.0-flash",
                        system_instruction=system_prompt
                    )

                    # Pass the user's code to the model
                    response = model.generate_content(
                        input_code,
                        generation_config=genai.types.GenerationConfig(
                            candidate_count=1,
                            max_output_tokens=4096,
                        ),
                    )

                    # Sanitize and display the result
                    corrected_code = sanitize_response(response.text)

                    if corrected_code:
                        st.subheader("Corrected Code")
                        st.code(corrected_code, language="python")
                    else:
                        st.warning("The AI returned an empty response. Please try again.")

            # Handle specific API errors
            except google_api_exceptions.GoogleAPIError as e:
                st.error(f"Google API Error: {e}")
            # Handle any other errors
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
