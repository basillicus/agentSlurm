from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum


class Severity(str, Enum):
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"


class UserProfile(str, Enum):
    BASIC = "Basic"
    MEDIUM = "Medium"
    ADVANCED = "Advanced"


class ParsedElement(BaseModel):
    element_type: str  # 'SBATCH', 'COMMAND', 'VARIABLE', etc.
    key: Optional[str] = None
    value: Optional[str] = None
    line_number: int
    raw_line: str


class Finding(BaseModel):
    agent_id: str
    rule_id: str
    severity: Severity
    title: str
    message: str
    line_number: Optional[int] = None
    confidence: float = 1.0
    documentation_url: Optional[str] = None
    category: Optional[str] = None


class UserCommand(BaseModel):
    message: str
    line_number: int
    intent: Optional[str] = None  # 'question', 'code_generation', etc.


class WorkflowInference(BaseModel):
    name: str
    confidence: float
    tools: List[str]


class JobContext(BaseModel):
    # Input data
    raw_script: str
    user_profile: UserProfile = UserProfile.MEDIUM

    # Parsed data
    parsed_elements: List[ParsedElement] = Field(default_factory=list)
    user_commands: List[UserCommand] = Field(default_factory=list)

    # Analysis results
    inferred_workflow: Optional[WorkflowInference] = None
    findings: List[Finding] = Field(default_factory=list)
    responses: List[Dict[str, Any]] = Field(default_factory=list)

    # Tracing and debugging
    trace_log: List[Dict[str, Any]] = Field(default_factory=list)
    script_path: Optional[str] = None

    # Additional metadata
    execution_id: Optional[str] = None
    timestamp: Optional[str] = None

