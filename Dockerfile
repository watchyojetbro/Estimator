
FROM python:3.9-slim


RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    libgl1\
    && rm -rf /var/lib/apt/lists/*


ENV TESSDATA_PREFIX /usr/share/tesseract-ocr/4.00/tessdata
ENV TESSERACT_CMD /usr/bin/tesseract


WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY ./flask .


EXPOSE 5000


CMD ["python", "main.py"]