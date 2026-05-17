from uagents import Model
from typing import Optional


class Vulnerability(Model):
    """A single security issue found in the code."""
    type: str              
    severity: str          
    line_number: Optional[int] = None
    description: str
    suggested_fix: str


class ScanRequest(Model):
    """Sent by the requester to ask for a security scan."""
    code: str
    language: str = "python"
    filename: Optional[str] = None


class ScanResponse(Model):
    """Returned by the scanner with the analysis result."""
    scan_status: str                         
    vulnerabilities: list[Vulnerability] = []
    summary: str = ""
    error_message: Optional[str] = None