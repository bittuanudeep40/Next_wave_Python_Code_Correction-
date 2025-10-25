import os
import sys
import google.generativeai as genai
from google.api_core import exceptions as google_api_exceptions
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Configure the Gemini API
try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        sys.exit("Error: GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    sys.exit(f"Error configuring Generative AI: {e}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/correct", methods=["POST"])
def correct_code():
    try:
        data = request.json
        if not data or "code" not in data or "prompt" not in data:
            return jsonify({"error": "Invalid request payload."}), 400

        user_code = data.get("code")
        system_prompt = data.get("prompt")

        # Create the model *inside* the request
        # with the dynamic system prompt
        model = genai.GenerativeModel(
            "gemini-2.0-flash", system_instruction=system_prompt  # <-- THE FIX IS HERE
        )

        # Now, just pass the user's code to generate_content
        response = model.generate_content(
            user_code,
            generation_config=genai.types.GenerationConfig(
                candidate_count=1,
                max_output_tokens=4096,
            ),
        )

        return jsonify({"corrected_code": response.text})

    # Catch specific API errors
    except google_api_exceptions.GoogleAPIError as e:
        app.logger.error(f"Google API Error: {e}")
        return jsonify({"error": f"Google API Error: {e}"}), 500
    # Catch any other unexpected errors
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
