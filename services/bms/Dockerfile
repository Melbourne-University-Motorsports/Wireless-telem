FROM python:3.13-slim AS production

WORKDIR /bms_telemetry

COPY bms_telemetry/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the core scripts, no tests, no debug tools
COPY bms_telemetry/ .

CMD ["python", "main.py"]
