from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import google.generativeai as genai
import PyPDF2
import docx
from dotenv import load_dotenv
from io import BytesIO
import base64
from typing import Optional

load_dotenv()

app = FastAPI(title="MuseCareer API for Appsmith")

# CORS middleware - Configure for Appsmith
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://boikanyomz23.appsmith.com/app/musecareer/page1-691c7627102edd66cd768b0d?branch=main&environment=production"],  # Appsmith domain in production
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
    analysis: str
    model: str
    extracted_text_length: int

class TextAnalysisRequest(BaseModel):
    cv_text: str
    filename: Optional[str] = "manual_input.txt"

def extract_text_from_pdf(file_content):
    """Extract text from PDF"""
    try:
        pdf_reader = PyPDF2.PdfReader(file_content)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading PDF: {str(e)}")

def extract_text_from_docx(file_content):
    """Extract text from DOCX"""
    try:
        doc = docx.Document(file_content)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading DOCX: {str(e)}")

def generate_career_analysis(cv_text: str) -> str:
    """Generate career analysis using Gemini API"""
    prompt = f"""You are an expert career counselor and CV reviewer. Analyze this CV/resume and provide comprehensive feedback.

CV Content:
{cv_text}

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

Please be specific, encouraging, and constructive in your feedback. Use clear formatting and bullet points where appropriate."""

    response = model.generate_content(prompt)
    
    if not response or not response.text:
        raise HTTPException(status_code=500, detail="AI service returned no response")
    
    return response.text

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
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model": "gemini-1.5-pro",
        "api_key_configured": bool(GEMINI_API_KEY)
    }

@app.post("/analyze-cv", response_model=AnalysisResponse)
async def analyze_cv_file(file: UploadFile = File(...)):
    """
    Analyze CV from uploaded file (PDF, DOCX, TXT)
    Use this endpoint with Appsmith's File Picker widget
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        file_ext = file.filename.lower().split('.')[-1]
        if file_ext not in ['pdf', 'docx', 'txt']:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file format. Please upload PDF, DOCX, or TXT"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Extract text based on file type
        if file_ext == 'pdf':
            cv_text = extract_text_from_pdf(BytesIO(file_content))
        elif file_ext == 'docx':
            cv_text = extract_text_from_docx(BytesIO(file_content))
        else:  # txt
            cv_text = file_content.decode('utf-8')
        
        # Validate extracted text
        if not cv_text or len(cv_text.strip()) < 50:
            raise HTTPException(
                status_code=400, 
                detail="Could not extract enough text from the CV. Please ensure the file contains readable text."
            )
        
        # Generate analysis using Gemini
        analysis = generate_career_analysis(cv_text)
        
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
        print(f"Error during analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/analyze-cv-base64", response_model=AnalysisResponse)
async def analyze_cv_base64(
    file_data: str = Form(...),
    filename: str = Form(...),
):
    """
    Analyze CV from base64 encoded file data
    Alternative endpoint for Appsmith file upload
    """
    try:
        # Decode base64 file data
        file_content = base64.b64decode(file_data)
        
        file_ext = filename.lower().split('.')[-1]
        if file_ext not in ['pdf', 'docx', 'txt']:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file format. Please upload PDF, DOCX, or TXT"
            )
        
        # Extract text based on file type
        if file_ext == 'pdf':
            cv_text = extract_text_from_pdf(BytesIO(file_content))
        elif file_ext == 'docx':
            cv_text = extract_text_from_docx(BytesIO(file_content))
        else:  # txt
            cv_text = file_content.decode('utf-8')
        
        # Validate extracted text
        if not cv_text or len(cv_text.strip()) < 50:
            raise HTTPException(
                status_code=400, 
                detail="Could not extract enough text from the CV. Please ensure the file contains readable text."
            )
        
        # Generate analysis using Gemini
        analysis = generate_career_analysis(cv_text)
        
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
        print(f"Error during analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/analyze-cv-text", response_model=AnalysisResponse)
async def analyze_cv_text(request: TextAnalysisRequest):
    """
    Analyze CV from raw text input
    Use this if user pastes CV text directly in Appsmith text area
    """
    try:
        cv_text = request.cv_text.strip()
        
        # Validate text
        if not cv_text or len(cv_text) < 50:
            raise HTTPException(
                status_code=400, 
                detail="Please provide at least 50 characters of CV text"
            )
        
        # Generate analysis using Gemini
        analysis = generate_career_analysis(cv_text)
        
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
        print(f"Error during analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
