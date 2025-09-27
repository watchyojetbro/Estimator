from flask import Flask, render_template, request, redirect, url_for, session
import cv2
import pytesseract
from pytesseract import Output
from pathlib import Path
import json
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
            nums.append(int(t.strip()))

    return nums

def extract_grades_from_image_path(path: Path) -> list[int]:
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return text_extraction(img)

folder = Path("AUD")
images = sorted([p for p in folder.iterdir()
                 if p.suffix.lower() in {".png", ".jpg", ".jpeg"}])

results: dict[str, list[int]] = {}
for p in images:
    name = p.stem  #removing suffix
    grades = extract_grades_from_image_path(p)
    results[name] = grades
    print(f"{name}: {grades}")


# three specific arrays (empty list if that file wasn't found/parsed)
SoSe23   = results.get("SoSe23", [])
SoSe24   = results.get("SoSe24", [])
WiSe2425 = results.get("WiSe2425", [])





