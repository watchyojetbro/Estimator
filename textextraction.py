from flask import Flask, render_template, request
import cv2
import sqlite3
from pathlib import Path
import pytesseract
from pytesseract import Output
#------------------------Image transformation to black text on white background---------------------
def to_black_text_on_white(img):
    #Grayscale with Gaussianblur
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    #Otsu threshold
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    #Normalisation(incase the screenshot is in dark mode)
    if (bw == 255).mean() < 0.5:
        bw = cv2.bitwise_not(bw)

    return bw
#-------------------------Extraction of the numerical values(number of students with certain grade) from image--------------
def text_extraction(img):
    imgv2 = to_black_text_on_white(img)
    cfg = "--psm 6 -l deu+eng"

    data = pytesseract.image_to_data(imgv2, output_type=Output.DICT, config=cfg)
    #Parse the page for the Anzahl word
    idx = -1
    for i, t in enumerate(data["text"]):
        if t and t.strip().lower() == "anzahl":
            idx = i; break
    #Select the line where Anzahl was found
    b = data["block_num"][idx]
    p = data["par_num"][idx]
    ln = data["line_num"][idx]
    #extracting the number of students corresponding to each grade
    same_line_idx = [i for i in range(len(data["text"]))
                     if data["block_num"][i] == b and

                     data["par_num"][i] == p and
                     data["line_num"][i] == ln]
    same_line_idx.sort(key=lambda i: data["left"][i])
    nums = []
    for i in same_line_idx:
        t = data["text"][i]
        if t and t.strip().isdigit():
            nums.append(t.strip())

    return nums

DB_COLS = ["g_1_0","g_1_3","g_1_7","g_2_0","g_2_3",
           "g_2_7","g_3_0","g_3_3","g_3_7","g_4_0","g_5_0"]

class Semester:
    def __init__(self, name: str, grades: list[int]):
        if len(grades) != len(DB_COLS):
            raise ValueError(f"Expected {len(DB_COLS)} grade counts, got {len(grades)}")
        self.name = name                 # e.g. "SoSe23" or "WiSe2425"
        self.grades = grades             # list of 11 ints in DB_COLS order

    @classmethod
#--------------------------extracting the array and turning the values into integers-----------------------
    def from_image(cls, name: str, image_path: str):
        img = cv2.imread(image_path)
        nums = text_extraction(img)          # ['30','25',...,'184']
        grades_int = [int(x) for x in nums]  # -> [30,25,...,184]
        return cls(name=name, grades=grades_int)

    def save_sqlite(self, db_path: str, table: str = "AUD"):
        # open connection (beginner style: assign it directly, not with context manager)
        con = sqlite3.connect(db_path)

        # get a cursor
        cur = con.cursor()

        # create table if it does not exist
        cur.execute("CREATE TABLE IF NOT EXISTS AUD ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "semester_name TEXT NOT NULL UNIQUE,"
                    "g_1_0 INTEGER, g_1_3 INTEGER, g_1_7 INTEGER,"
                    "g_2_0 INTEGER, g_2_3 INTEGER, g_2_7 INTEGER,"
                    "g_3_0 INTEGER, g_3_3 INTEGER, g_3_7 INTEGER,"
                    "g_4_0 INTEGER, g_5_0 INTEGER"
                    ")")

        # build the INSERT command (explicitly, piece by piece)
        cols = "semester_name," + ",".join(DB_COLS)
        placeholders = ",".join(["?"] * (1 + len(DB_COLS)))
        sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"

        # execute the insert
        cur.execute(sql, (self.name, *self.grades))

        # commit and close
        con.commit()
        con.close()


# -------------------- batch process the AUD folder --------------------

def import_aud_folder(folder: str, db_path: str = "grades.db"):
    folder_path = Path(folder)
    image_paths = sorted(p for p in folder_path.iterdir()
                         if p.suffix.lower() in {".png", ".jpg", ".jpeg"})

    for p in image_paths:
        semester_name = p.stem  # e.g. "SoSe23" (file name without extension)
        try:
            sem = Semester.from_image(semester_name, str(p))
            sem.save_sqlite(db_path, table="AUD")
            print(f"Saved {semester_name}: {sem.grades}")
        except Exception as e:
            print(f"Failed {semester_name}: {e}")

# ---------- run it ----------
if __name__ == "__main__":
    import_aud_folder("AUD", db_path="grades.db")


