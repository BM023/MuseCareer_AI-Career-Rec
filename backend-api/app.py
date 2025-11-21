from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from mangum import Mangum
import google.generativeai as genai
import PyPDF2
import docx
from dotenv import load_dotenv
from io import BytesIO
import base64
from typing import Optional
import json
from starlette.concurrency import run_in_threadpool
from datetime import datetime


SAMPLE_CV_PATH = r"C:\Users\luyan\Documents\Luyanda_Dev\capaciti projects\cv_sample.pdf"

load_dotenv()

app = FastAPI(title="MuseCareer API for Appsmith")

# CORS middleware - Configure for Appsmith
ALLOWED_ORIGINS = [
    "https://boikanyomz23.appsmith.com",  # production Appsmith origin
    "http://localhost:3000",              # local testing
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

# Pydantic models for request/response
class AnalysisResponse(BaseModel):
    success: bool
    filename: str
    analysis: str  # JSON string or raw text
    model: str
    extracted_text_length: int

class TextAnalysisRequest(BaseModel):
    cv_text: str
    filename: Optional[str] = "manual_input.txt"
    interests: Optional[str] = ""

# Prompt building & JSON guidance suffix
JSON_PROMPT_SUFFIX = """
IMPORTANT: Please respond with a single VALID JSON object only (no extra commentary).
The JSON object must contain these top-level keys:
- skills_summary,
- experience_level,
- career_recommendations,
- cv_improvement_feedback,
- skills_gap_analysis,
- action_plan

Each key should contain structured values (lists / nested objects) so the API consumer can parse them programmatically.
Return only the JSON object and nothing else.
"""

BASE_PROMPT_TEMPLATE = """You are an expert career counselor and CV reviewer. Analyze this CV/resume and provide comprehensive feedback.

CV Content:
{cv_text}

User interests: {interests}

Please provide a detailed analysis with the following sections:

**SKILLS SUMMARY**
List and categorize the key skills identified (technical, soft skills, tools, languages, etc.)

**EXPERIENCE LEVEL**
Assess whether this candidate is: Junior (0-2 years), Mid-level (3-5 years), Senior (6-10 years), or Executive (10+ years)
Provide reasoning for your assessment.

**CAREER RECOMMENDATIONS**
Suggest 3 specific career paths or roles that match their profile. For each recommendation:
- Job title
- Why it's a good fit
- Typical salary range (if applicable)
- Growth potential

**CV IMPROVEMENT FEEDBACK**
Provide specific, actionable suggestions to improve their CV:
- What's working well
- What's missing or unclear
- Formatting suggestions
- Content recommendations
- Keywords to add for ATS systems

**SKILLS GAP ANALYSIS**
Identify 3-5 skills they should develop or strengthen for their target roles:
- Skill name
- Why it's important
- How to acquire it (courses, certifications, practice)

**ACTION PLAN**
Provide a clear 3-month action plan with specific steps they can take immediately.

Please be specific, encouraging, and constructive in your feedback. Use clear formatting and bullet points where appropriate.
"""

def _build_prompt(cv_text: str, interests: Optional[str] = "") -> str:
    # Combine base prompt and JSON instruction suffix
    full = BASE_PROMPT_TEMPLATE.format(cv_text=cv_text, interests=interests or "")
    return full + "\n\n" + JSON_PROMPT_SUFFIX

# Extractors
def extract_text_from_pdf(file_content):
    """Extract text from PDF safely (PyPDF2 may return None for pages)."""
    try:
        # Accept either BytesIO or raw bytes
        if isinstance(file_content, (bytes, bytearray)):
            fp = BytesIO(file_content)
        else:
            fp = file_content
        reader = PyPDF2.PdfReader(fp)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        # Log server-side for debugging
        app.logger.error("PDF extraction error: %s", str(e))
        raise HTTPException(status_code=400, detail=f"Error reading PDF: {str(e)}")

def extract_text_from_docx(file_content):
    """Extract text from DOCX"""
    try:
        if isinstance(file_content, (bytes, bytearray)):
            fp = BytesIO(file_content)
        else:
            fp = file_content
        doc = docx.Document(fp)
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        return "\n".join(paragraphs)
    except Exception as e:
        app.logger.error("DOCX extraction error: %s", str(e))
        raise HTTPException(status_code=400, detail=f"Error reading DOCX: {str(e)}")

# Model call wrapper (blocking inside threadpool)
def _call_model_blocking(prompt: str) -> str:
    """Blocking call to Gemini SDK. Runs inside a threadpool."""
    try:
        response = model.generate_content(prompt)
       
        if not response or not getattr(response, "text", None):
            raise RuntimeError("AI service returned no response text")
        return response.text
    except Exception as e:
        app.logger.error("Model call failed: %s", str(e))
        
        raise RuntimeError(f"Model call failed: {str(e)}")

async def generate_career_analysis(cv_text: str, interests: Optional[str] = "") -> str:
    """
    Prepare prompt, run blocking model call in threadpool, attempt to parse JSON.
    Returns a JSON string on success, or raw text when parsing fails.
    """
    # Prevent extremely large inputs — truncate with note
    max_chars = 40000  # tune according to token usage and cost
    if len(cv_text) > max_chars:
        cv_text = cv_text[:max_chars] + "\n\n[TRUNCATED]"
    prompt = _build_prompt(cv_text, interests)
    # Run blocking call safely
    text = await run_in_threadpool(_call_model_blocking, prompt)
    # Try to parse as JSON 
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, ensure_ascii=False)
    except Exception:
        # If parsing fails, return raw text so client can show / debug
        app.logger.warning("Model returned non-JSON output; returning raw text for client: %s", text[:500])
        return text

# Endpoints
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "MuseCareer API for Appsmith",
        "version": "1.0",
        "endpoints": {
            "health": "/health",
            "analyze_cv_file": "/analyze-cv (POST)",
            "analyze_cv_text": "/analyze-cv-text (POST)",
            "analyze_cv_base64": "/analyze-cv-base64 (POST)"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint (do not expose secrets)"""
    return {
        "status": "healthy",
        "model": "gemini-1.5-pro",
        "api_key_configured": bool(GEMINI_API_KEY),
        "time": datetime.utcnow().isoformat() + "Z"
    }

@app.post("/analyze-cv", response_model=AnalysisResponse)
async def analyze_cv_file(
    file: UploadFile = File(...),
    interests: Optional[str] = Form(None)
):
    """
    Analyze CV from uploaded file (PDF, DOCX, TXT)
    Use this endpoint with Appsmith's File Picker widget.
    Optional 'interests' can be sent as an additional form field.
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        file_ext = file.filename.lower().split('.')[-1]
        if file_ext not in ['pdf', 'docx', 'txt', 'doc']:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file format. Please upload PDF, DOCX, or TXT"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Extract text based on file type
        if file_ext == 'pdf':
            cv_text = extract_text_from_pdf(file_content)
        elif file_ext in ('docx', 'doc'):
            cv_text = extract_text_from_docx(file_content)
        else:  # txt
            cv_text = file_content.decode('utf-8')
        
        # Validate extracted text
        if not cv_text or len(cv_text.strip()) < 50:
            raise HTTPException(
                status_code=400, 
                detail="Could not extract enough text from the CV. Please ensure the file contains readable text."
            )
        
        # Generate analysis using Gemini (async)
        try:
            analysis = await generate_career_analysis(cv_text, interests or "")
        except RuntimeError as e:
            app.logger.error("Model error: %s", str(e))
            raise HTTPException(status_code=502, detail=f"Upstream AI error: {str(e)}")
        
        return AnalysisResponse(
            success=True,
            filename=file.filename,
            analysis=analysis,
            model="gemini-1.5-pro",
            extracted_text_length=len(cv_text)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        app.logger.error("Unhandled error during analysis: %s", str(e))
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/analyze-cv-base64", response_model=AnalysisResponse)
async def analyze_cv_base64(
    file_data: str = Form(...),
    filename: str = Form(...),
    interests: Optional[str] = Form(None),
):
    """
    Analyze CV from base64 encoded file data
    Alternative endpoint for Appsmith file upload where you send base64 file content.
    """
    try:
        # Decode base64 file data
        try:
            file_content = base64.b64decode(file_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 data: {str(e)}")
        
        file_ext = filename.lower().split('.')[-1]
        if file_ext not in ['pdf', 'docx', 'txt', 'doc']:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file format. Please upload PDF, DOCX, or TXT"
            )
        
        # Extract text based on file type
        if file_ext == 'pdf':
            cv_text = extract_text_from_pdf(file_content)
        elif file_ext in ('docx', 'doc'):
            cv_text = extract_text_from_docx(file_content)
        else:  # txt
            cv_text = file_content.decode('utf-8')
        
        # Validate extracted text
        if not cv_text or len(cv_text.strip()) < 50:
            raise HTTPException(
                status_code=400, 
                detail="Could not extract enough text from the CV. Please ensure the file contains readable text."
            )
        
        # Generate analysis using Gemini (async)
        try:
            analysis = await generate_career_analysis(cv_text, interests or "")
        except RuntimeError as e:
            app.logger.error("Model error: %s", str(e))
            raise HTTPException(status_code=502, detail=f"Upstream AI error: {str(e)}")
        
        return AnalysisResponse(
            success=True,
            filename=filename,
            analysis=analysis,
            model="gemini-1.5-pro",
            extracted_text_length=len(cv_text)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        app.logger.error("Unhandled error during base64 analysis: %s", str(e))
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/analyze-cv-text", response_model=AnalysisResponse)
async def analyze_cv_text(request: TextAnalysisRequest):
    """
    Analyze CV from raw text input (when user pastes CV text).
    """
    try:
        cv_text = request.cv_text.strip()
        
        # Validate text
        if not cv_text or len(cv_text) < 50:
            raise HTTPException(
                status_code=400, 
                detail="Please provide at least 50 characters of CV text"
            )
        
        # Generate analysis using Gemini (async)
        try:
            analysis = await generate_career_analysis(cv_text, request.interests or "")
        except RuntimeError as e:
            app.logger.error("Model error: %s", str(e))
            raise HTTPException(status_code=502, detail=f"Upstream AI error: {str(e)}")
        
        return AnalysisResponse(
            success=True,
            filename=request.filename,
            analysis=analysis,
            model="gemini-1.5-pro",
            extracted_text_length=len(cv_text)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        app.logger.error("Unhandled error during text analysis: %s", str(e))
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Wrap FastAPI with Mangum for AWS Lambda
handler = Mangum(app)

# Run locally
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
