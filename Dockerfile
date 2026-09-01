FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --no-cache-dir --upgrade \
    pip3 \
    setuptools>=78.1.1 \
    wheel

RUN pip3 install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8080

CMD ["python", "src/app.py"]
