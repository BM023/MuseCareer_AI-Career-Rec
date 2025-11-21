# utils/extractor.py
import io
from typing import Optional
import pdfplumber
import docx

def extract_text_from_pdf(file_stream: io.BytesIO) -> str:
    text_parts = []
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)

def extract_text_from_docx(file_stream: io.BytesIO) -> str:
    doc = docx.Document(file_stream)
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    return "\n".join(paragraphs)

def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Detect PDF vs DOCX by filename extension.
    Returns extracted plain text.
    """
    name = filename.lower()
    stream = io.BytesIO(file_bytes)
    if name.endswith(".pdf"):
        return extract_text_from_pdf(stream)
    if name.endswith(".docx") or name.endswith(".doc"):
        return extract_text_from_docx(stream)
    # fallback: try pdf first then docx
    try:
        return extract_text_from_pdf(stream)
    except Exception:
        stream.seek(0)
        return extract_text_from_docx(stream)
