FROM python:3.11-slim
WORKDIR /app
COPY . .

# Editable, not a plain install. workflow_path() and PROFILES_DIR resolve
# workflows/ and profiles/ relative to the autornd package directory, and
# neither ships inside the package — they are repo files the operator edits.
# A relocating install therefore leaves both pointing at paths that do not
# exist; editable keeps one copy of the tree at /app and both resolve.
#
# pyproject.toml is now the only dependency manifest. The dev extra is
# deliberately omitted, so no test framework reaches the image — installing
# from the old requirements.txt put pytest and pytest-asyncio in production.
RUN pip install --no-cache-dir -e .

EXPOSE 8100
CMD ["uvicorn", "autornd.main:app", "--host", "0.0.0.0", "--port", "8100"]
