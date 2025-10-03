from flask import Flask, render_template, request, jsonify
import cv2
import pytesseract
from pytesseract import Output
from pathlib import Path
import logging

# Set up logging for basic status updates
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Global Config and Data Structures ---
# These are the grades we track, from best to worst.
GRADES = ["1.0", "1.3", "1.7", "2.0", "2.3", "2.7", "3.0", "3.3", "3.7", "4.0"]
NUM_GRADES = len(GRADES)  # Should be 10

# Will hold the aggregated student counts for all 10 grades across all semesters.
CUMULATIVE_COUNTS = [0] * NUM_GRADES
TOTAL_STUDENTS = 0


# --- OCR Utility Functions ---

def clean_for_ocr(img):

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # Use Otsu's method for automatic thresholding
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Invert colors if the screenshot is dark mode
    if (bw == 255).mean() < 0.5:
        bw = cv2.bitwise_not(bw)
    return bw


def extract_numbers_from_anzahl_line(img):
    """Finds 'Anzahl' and extracts numbers (student counts) on the same line."""
    cleaned_img = clean_for_ocr(img)
    cfg = "--psm 6 -l deu+eng"  # PSM 6 for a single block of text

    data = pytesseract.image_to_data(cleaned_img, output_type=Output.DICT, config=cfg)

    # Look for the German word for count
    idx = -1
    for i, t in enumerate(data["text"]):
        if t and t.strip().lower() == "anzahl":
            idx = i
            break

    if idx == -1:
        logging.warning("Couldn't find 'Anzahl' in the image. Skipping.")
        return []

    # Get the line coordinates for 'Anzahl'
    b = data["block_num"][idx]
    p = data["par_num"][idx]
    ln = data["line_num"][idx]

    # Find all text elements on that line
    line_indices = [i for i in range(len(data["text"]))
                    if data["block_num"][i] == b and
                    data["par_num"][i] == p and
                    data["line_num"][i] == ln]
    line_indices.sort(key=lambda i: data["left"][i])  # Sort by position (left-to-right)

    # Collect the numbers
    nums = []
    for i in line_indices:
        t = data["text"][i]
        if t and t.strip().isdigit():
            nums.append(int(t.strip()))

    return nums[:NUM_GRADES]  # Only take the first 10, corresponding to our grades


def scan_image_for_grades(path: Path) -> list[int]:
    """Reads image file and extracts the grade counts."""
    # Read the image using OpenCV
    img = cv2.imread(str(path))
    return extract_numbers_from_anzahl_line(img)


# --- 4. Data Aggregation & Initialization ---

def init_data_from_images():
    """Scans images in the 'AUD' folder, aggregates results, and sets global counts."""
    global CUMULATIVE_COUNTS, TOTAL_STUDENTS


    logging.info("Initializing grade data from image scans...")
    # Check for images in the 'AUD' folder relative to this script
    img_folder = Path("AUD")
    images = sorted([p for p in img_folder.iterdir()
                     if p.suffix.lower() in {".png", ".jpg", ".jpeg"}])

    semester_results = {}
    for p in images:

            counts = scan_image_for_grades(p)
            semester_results[p.stem] = counts
            logging.info(f"Scanned {p.stem}: {counts}")

    # Map specific semesters for aggregation (needs filenames SoSe23, etc.)
    sem_23_summer = semester_results.get("SoSe23", [])
    sem_24_summer = semester_results.get("SoSe24", [])
    sem_25_winter = semester_results.get("WiSe2425", [])

    all_data = [sem_23_summer, sem_24_summer, sem_25_winter]

    # Aggregate counts across all semesters
    temp_counts = [0] * NUM_GRADES
    for sem_data in all_data:
            for i in range(NUM_GRADES):
                temp_counts[i] += sem_data[i]


    # Finalize globals
    CUMULATIVE_COUNTS = temp_counts
    TOTAL_STUDENTS = sum(CUMULATIVE_COUNTS)

    logging.info(f"Data loading complete. Total tracked students: {TOTAL_STUDENTS}")



# Run the data setup immediately when the script executes
init_data_from_images()


# --- 5. Calculation Logic ---

def get_success_percent(target_grade: str) -> int:
    """Calculates the percentage of students who scored target_grade or better."""

    # Basic input check
    if target_grade not in GRADES or TOTAL_STUDENTS == 0:
        return 0

    try:
        target_idx = GRADES.index(target_grade)

        # Sum of students who achieved a grade better than or equal to the target
        students_passed_or_equal = sum(CUMULATIVE_COUNTS[:target_idx + 1])

        percent = (students_passed_or_equal / TOTAL_STUDENTS) * 100

        # Return as an integer, rounded nicely
        return int(round(percent))

    except ValueError:
        logging.error(f"Grade check failed for: {target_grade}")
        return 0


# --- 6. Flask Setup and API Routes ---

app = Flask(__name__)


# Main entry point for the landing page
@app.route('/')
def home():
    """Renders the basic home page template."""
    return render_template('home.html')


# Main entry point for the estimator tool
@app.route('/estimator')
def estimator():
    """Renders the estimator page where the magic happens."""
    return render_template('estimator.html')


# API endpoint for the frontend to get the percentage
@app.route('/api/calculate_percentage', methods=['POST'])
def calculate_percentage_api():
    """Handles the user's grade selection and returns the calculated percentage."""
    try:
        data = request.json
        selected_score = data.get('score')

        # Validate input against our known grades
        if not selected_score or selected_score not in GRADES:
            return jsonify({'message': 'Invalid grade selected.', 'status': 'error'}), 400

        # Calculate the result using the aggregated OCR data
        percentage_result = get_success_percent(selected_score)

        # Send the clean result back to the frontend
        return jsonify({
            'percentage': percentage_result,
            'status': 'success',
            'grade': selected_score
        }), 200

    except Exception as e:
        # Generic error handling for internal issues
        logging.error(f"API processing failed: {e}", exc_info=True)
        return jsonify({'message': 'Server encountered an internal error.', 'status': 'error', 'percentage': 0}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)