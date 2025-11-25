import base64
import io
import os
import requests
from typing import Any, Optional

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


def extract_text_from_pdf(pdf_bytes: bytes, logger=None) -> str:
    """
    Extract text from PDF bytes.
    Tries pdfplumber first (better for complex PDFs), falls back to PyPDF2.
    """
    if not pdf_bytes:
        return "Error: No PDF data provided"
    
    text_content = []
    
    # Try pdfplumber first (better text extraction)
    if HAS_PDFPLUMBER:
        try:
            if logger:
                logger.info("Extracting text using pdfplumber...")
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        text_content.append(f"--- Page {page_num} ---\n{text}\n")
            if text_content:
                return "\n".join(text_content)
        except Exception as e:
            if logger:
                logger.warning(f"pdfplumber extraction failed: {e}, trying PyPDF2...")
    
    # Fallback to PyPDF2
    if HAS_PYPDF2:
        try:
            if logger:
                logger.info("Extracting text using PyPDF2...")
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text()
                if text:
                    text_content.append(f"--- Page {page_num} ---\n{text}\n")
            
            if text_content:
                return "\n".join(text_content)
        except Exception as e:
            if logger:
                logger.error(f"PyPDF2 extraction failed: {e}")
            return f"Error extracting text from PDF: {e}"
    
    # If neither library is available
    return "Error: No PDF extraction library available. Please install pdfplumber or PyPDF2."


def get_pdf_text(content: list[dict[str, Any]], logger=None) -> str | None:
    """
    Process content items and extract text from PDF resources.
    """
    if logger:
        logger.info(f"Processing {len(content)} content items for PDF extraction")

    extracted_texts = []

    for item in content:
        if item.get("type") == "resource":
            mime_type = item.get("mime_type", "")
            if logger:
                logger.info(f"Processing resource with mime type: {mime_type}")
            
            if mime_type == "application/pdf" or mime_type.endswith("/pdf"):
                if logger:
                    logger.info(f"Extracting text from PDF - Content length: {len(item.get('contents', ''))} characters")
                
                # Decode base64 PDF content
                try:
                    pdf_base64 = item.get("contents", "")
                    pdf_bytes = base64.b64decode(pdf_base64)
                    if logger:
                        logger.info(f"Decoded PDF: {len(pdf_bytes)} bytes")
                    
                    # Extract text from PDF
                    pdf_text = extract_text_from_pdf(pdf_bytes, logger=logger)
                    extracted_texts.append(pdf_text)
                    
                except Exception as e:
                    error_msg = f"Error processing PDF: {e}"
                    if logger:
                        logger.error(error_msg)
                    extracted_texts.append(error_msg)

    # Combine extracted text
    if extracted_texts:
        return "\n\n".join(extracted_texts)
    else:
        return "No PDF content found to extract."


def summarize_text(text: str, logger=None) -> Optional[str]:
    """
    Summarize text using ASI One API.
    Returns the summarized text or None if summarization fails.
    """
    if not text or not text.strip():
        return None
    
    api_key = os.getenv("ASI_ONE_API_KEY")
    if not api_key:
        if logger:
            logger.error("ASI_ONE_API_KEY not found in environment variables")
        return None
    
    url = "https://api.asi1.ai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-session-id": "pdf-summarization-session",
        "Content-Type": "application/json"
    }
    
    # Create a prompt for summarization
    # If text is very long, we might need to truncate it
    max_length = 100000  # Adjust based on model limits
    text_to_summarize = text[:max_length] if len(text) > max_length else text
    
    prompt = f"""Please provide a concise summary of the following PDF content. 
Focus on the main points, key information, and important details.

PDF Content:
{text_to_summarize}

Summary:"""
    
    json_data = {
        "model": "asi1-mini",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        if logger:
            logger.info("Sending summarization request to ASI One API...")
        
        response = requests.post(url, headers=headers, json=json_data, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        summary = result["choices"][0]["message"]["content"]
        
        if logger:
            logger.info(f"Summarization complete. Summary length: {len(summary)} characters")
        
        return summary
        
    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"Failed to summarize text: {e}")
        return None
    except KeyError as e:
        if logger:
            logger.error(f"Unexpected response format from ASI One API: {e}")
        return None
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error during summarization: {e}")
        return None

