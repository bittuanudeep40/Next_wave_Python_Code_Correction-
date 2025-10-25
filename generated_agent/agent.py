import os
import subprocess
import logging
import shutil
import re
import sys
import google.generativeai as genai
from google.api_core import exceptions as google_api_exceptions

TARGET_DIR = "../target_project/"
TEST_DIR = "../test_suite/"
BACKUP_DIR = "../target_project_backup/"
MODEL_NAME = "gemini-2.0-flash"
MAX_ATTEMPTS = 3
LOG_FILE = "agent.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logging.error("GOOGLE_API_KEY environment variable not set.")
    sys.exit(1)

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)


def backup_project():
    """Creates a backup of the target project directory."""
    try:
        if os.path.exists(BACKUP_DIR):
            shutil.rmtree(BACKUP_DIR)
        shutil.copytree(TARGET_DIR, BACKUP_DIR)
        logging.info("Project backed up successfully.")
    except IOError as e:
        logging.error("Error backing up project: %s", e)
        raise


def restore_project():
    """Restores the target project directory from the backup."""
    try:
        if os.path.exists(BACKUP_DIR):
            if os.path.exists(TARGET_DIR):
                shutil.rmtree(TARGET_DIR)
            shutil.copytree(BACKUP_DIR, TARGET_DIR)
            logging.info("Project restored successfully.")
        else:
            logging.warning("Backup directory does not exist. Skipping restore.")
    except IOError as e:
        logging.error("Error restoring project: %s", e)
        raise


def run_tests():
    """Runs the pytest test suite."""
    try:
        # Use sys.executable to run pytest as a module
        result = subprocess.run(
            [sys.executable, "-m", "pytest", TEST_DIR],
            capture_output=True,
            text=True,
            check=False,
        )
        logging.info("Test run completed with return code: %s", result.returncode)
        return result
    except subprocess.CalledProcessError as e:
        logging.error("Error running tests: %s", e)
        raise


def generate_fix(stderr):
    """Generates a code fix based on the test error output."""
    try:
        match = re.search(r"(\.\/.*?\.py):", stderr)
        if not match:
            # Fallback if the path is not relative
            match = re.search(r"([\w\/\\]+\.py):", stderr)
            if not match:
                logging.error("Could not parse file path from error message.")
                return None, None

        file_path_from_error = match.group(1).replace("\\", "/")

        # Clean up the path
        if file_path_from_error.startswith("./"):
            file_path_from_error = file_path_from_error[2:]

        full_file_path = os.path.join(TARGET_DIR, file_path_from_error)

        if not os.path.exists(full_file_path):
            # Try to find the file if the path is partial
            for root, _, files in os.walk(TARGET_DIR):
                if os.path.basename(full_file_path) in files:
                    full_file_path = os.path.join(
                        root, os.path.basename(full_file_path)
                    )
                    logging.info("Found file at new path: %s", full_file_path)
                    break
            else:
                logging.error(
                    "File not found at path: %s (derived from: %s)",
                    full_file_path,
                    match.group(1),
                )
                return None, None

        try:
            with open(full_file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
        except IOError as e:
            logging.error("Error reading file: %s", e)
            return None, None

        prompt_lines = []
        prompt_lines.append(
            "You are an expert developer. Fix the code based on the error message.\n"
        )
        prompt_lines.append(f"The error is:\n{stderr}\n")
        prompt_lines.append(
            f"The code for {full_file_path} is:\n```python\n{source_code}\n```"
        )
        prompt_lines.append(
            (
                "\nProvide only the complete, corrected Python code for the file, "
                "without any explanations or markdown formatting like ```python."
            )
        )
        prompt = "".join(prompt_lines)

        try:
            response = model.generate_content(prompt)
            fixed_code = response.text
        except google_api_exceptions.GoogleAPIError as e:
            logging.error("Error generating fix: %s", e)
            return None, None

        fixed_code = fixed_code.replace("```python", "").replace("```", "").strip()

        return full_file_path, fixed_code

    except Exception as e:
        logging.error("An unexpected error occurred in generate_fix: %s", e)
        return None, None


def apply_fix(file_path, fixed_code):
    """Applies the generated fix to the specified file."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(fixed_code)
        logging.info("Applied fix to: %s", file_path)
    except IOError as e:
        logging.error("Error writing file: %s", e)
        raise


def main():
    """Main loop for the autonomous fixing agent."""
    try:
        backup_project()
    except IOError as e:
        logging.error("Failed to create initial backup. Exiting. Error: %s", e)
        return

    test_result = None
    for attempt in range(MAX_ATTEMPTS):
        logging.info("--- Attempt %s of %s ---", attempt + 1, MAX_ATTEMPTS)

        try:
            test_result = run_tests()
        except subprocess.CalledProcessError as e:
            logging.error("Failed to run tests. Exiting. Error: %s", e)
            restore_project()
            return

        if test_result.returncode == 0:
            logging.info("All tests passed! Project is fixed.")
            break

        logging.warning("Tests failed. Generating fix...")
        stderr = test_result.stderr
        if not stderr:
            stderr = test_result.stdout

        file_path, fixed_code = generate_fix(stderr)

        if not file_path or not fixed_code:
            logging.error("Failed to generate fix. Restoring project.")
            restore_project()
            break

        try:
            apply_fix(file_path, fixed_code)
        except IOError as e:
            logging.error("Failed to apply fix. Restoring. Error: %s", e)
            restore_project()
            break

        if attempt == MAX_ATTEMPTS - 1:
            logging.error(
                "Max attempts reached. Tests still failing. Restoring project."
            )
            restore_project()

    else:
        if test_result and test_result.returncode != 0:
            logging.error("Failed to fix the project after all attempts.")

    logging.info("Agent run finished.")


if __name__ == "__main__":
    main()
