import cv2
import sqlite3
from textextraction import text_extraction

conn = sqlite3.connect('grades.db')




img = cv2.imread("AUD/SoSe23.png")   # or SoSe23.png

print(text_extraction(img))
