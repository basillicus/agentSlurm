# AgentSlurm Developer Guide

## Overview

AgentSlurm is an intelligent, modular, and adaptive AI system designed to analyze SLURM job scripts in High-Performance Computing (HPC) environments. The system combines deterministic rule-based analysis with large language model (LLM) powered insights to provide comprehensive feedback and continuously improve its capabilities.

### Vision
The project aims to automate the analysis of SLURM job scripts, identify common errors and misconfigurations, and optimize resource utilization, especially concerning Lustre I/O patterns. It delivers actionable recommendations adjusted to the user's technical proficiency and maintains a modular architecture for easy expansion and component isolation.

### Core Objectives
- **Automated Analysis**: Parse and understand SLURM directives and shell commands.
- **Pitfall Detection**: Identify common errors, inconsistencies, and misconfigurations.
- **Optimization Identification**: Pinpoint opportunities for better resource utilization.
- **Tailored Feedback**: Deliver actionable recommendations based on user proficiency.
- **Modularity**: Maintain a modular agent-based architecture.
- **Continuous Learning**: Learn from user interactions and system feedback.

## 1. Core Architectural Principles

*   **Modularity (Agent-Based Design)**: The system is composed of independent, specialized "agents" (modules). Each agent has a specific responsibility (e.g., parsing, Lustre analysis, report generation). This allows for individual components to be developed, tested, evaluated, and updated in isolation.
*   **Data-Driven Pipeline**: The system operates as a data processing pipeline. A `JobContext` object is created for each script and is passed sequentially through the agents. Each agent enriches this object with its analysis, logs, and confidence scores.
*   **Traceability & Evaluation Hooks**: Every agent's decision, warning, and suggestion is logged with a unique ID, its inputs, and a confidence score. This creates a detailed trace for debugging and provides the raw data needed for robust evaluation (EVALS).
*   **Centralized Knowledge**: Agents are stateless. All "intelligence" (rules, heuristics, workflow patterns) is intended to be stored in a centralized, version-controlled Knowledge Base. Currently, rules are implemented within each agent, with the learning system designed to populate a persistent knowledge base file in the user's home directory.

## 2. Architecture

```
[SLURM Script] -> [Parser Agent] -> [Lustre Agent] -> [LLM Agent (optional)] -> [Learning Agent (optional)] -> [Synthesis Agent] -> [Report]
```

### Agent-Based Design

The system follows a modular, agent-based architecture where each component has a specific responsibility:

-   **Parser Agent**: Converts raw scripts to structured elements. Extracts `#SBATCH` directives and identifies commands as either tool commands or Lustre commands.
-   **Lustre Agent**: Analyzes file I/O patterns focusing on Lustre filesystem optimization, implementing LUSTRE-001 and LUSTRE-002 rules.
-   **LLM Agent**: Leverages large language models for deep analysis of complex patterns not caught by rule-based agents.
-   **Learning Agent**: Converts LLM insights into deterministic rules for the knowledge base.
-   **Synthesis Agent**: Consolidates findings and generates user reports.

### JobContext Data Model

The `JobContext` is the central data structure passed through the pipeline:
-   `raw_script`: The original script content.
-   `user_profile`: {level: 'Basic'/'Medium'/'Advanced'}.
-   `parsed_elements`: AST or structured representation of the script.
-   `user_commands`: A list of commands extracted from special comments (e.g., `# Agent SLURM: ...`).
-   `inferred_workflow`: {name: 'Variant Calling', confidence: 0.85, tools: ['bwa', 'samtools']}.
-   `findings`: A list of all issues/suggestions found by analysis agents. Each finding includes `{agent_id, rule_id, severity, message, line_number, confidence}`.
-   `responses`: A list of direct responses to user commands.
-   `trace_log`: A detailed log of each agent's execution for debugging and EVALS.

```python
class JobContext(BaseModel):
    # Input data
    raw_script: str
    user_profile: UserProfile = UserProfile.MEDIUM
    
    # Parsed data
    parsed_elements: List[ParsedElement] = []
    user_commands: List[UserCommand] = []
    
    # Analysis results
    inferred_workflow: Optional[WorkflowInference] = None
    findings: List[Finding] = []
    responses: List[Dict[str, Any]] = []
    
    # Tracing and debugging
    trace_log: List[Dict[str, Any]] = []
    script_path: Optional[str] = None
```

## LLM Integration and Learning System

The system implements a hybrid approach combining deterministic rule-based analysis with LLM-powered insights:

- **Rule-based agents** provide fast, reliable analysis for common patterns.
- **LLM agent** performs deeper analysis for complex or novel patterns not covered by rules.
- **Learning agent** converts LLM insights into new deterministic rules for the knowledge base.
- **Knowledge Base Updater** integrates learned rules into the central knowledge repository.

This creates a virtuous cycle where the system continuously expands its deterministic capabilities by learning from LLM explorations of novel patterns.

### Supported Providers for LLMAgent

The `LLMAgent` supports multiple providers:

#### OpenAI
- **Model**: Any GPT model (gpt-3.5-turbo, gpt-4, etc.)
- **Configuration**: Requires API key
- **Usage**: `--llm-provider openai --llm-model gpt-3.5-turbo --api-key YOUR_KEY`

#### Anthropic
- **Model**: Claude models (claude-3-sonnet, claude-3-opus, etc.)
- **Configuration**: Requires API key
- **Usage**: `--llm-provider anthropic --llm-model claude-3-sonnet --api-key YOUR_KEY`

#### Ollama
- **Model**: Any locally running model (llama2, mistral, etc.)
- **Configuration**: Optionally specify base URL (defaults to http://localhost:11434/v1)
- **Usage**: `--llm-provider ollama --llm-model llama2 --base-url http://localhost:11434/v1`

#### Hugging Face
- **Model**: Any text generation model from Hugging Face Hub
- **Configuration**: Requires API key for authenticated access, or use base_url for custom endpoints
- **Usage**:
  - With API key: `--llm-provider huggingface --llm-model microsoft/DialoGPT-medium --api-key YOUR_KEY`
  - With custom endpoint: `--llm-provider huggingface --base-url https://your-endpoint.hf.space --api-key YOUR_KEY`

### Learning Mechanism Implementation

The system's ability to learn is what makes it truly "agentic."

#### Knowledge Base Learning Process

*   **Insight Extraction**: The LLM agent identifies patterns and insights during its analysis.
*   **Rule Creation**: The learning agent analyzes LLM insights and converts them into structured rules with proper feedback for different user profiles.
*   **Integration**: The knowledge base updater validates and integrates new rules into the system's rule set, which are then applied in future deterministic analyses.

The learning mechanism is implemented in the `KnowledgeBaseUpdater` class in `agentSlurm/utils/knowledge_base_updater.py`.

## Current Analysis Features

### Lustre I/O Analysis

The Lustre Agent implements two core rules:

#### LUSTRE-001: Missing Lustre Striping for Large Files

**Detection**: When the script includes tools commonly used for processing large files (bwa, gatk, samtools, vasp, star, hisat2, bowtie2) but no `lfs setstripe` command is present.

**Feedback**: Provides tailored messages for Basic, Medium, and Advanced users about the importance of Lustre striping for large-file workloads.

#### LUSTRE-002: Inappropriate Wide Striping for Small Files

**Detection**: When the script includes tools commonly used for processing many small files (fastqc, multiqc, blastn, blastp, diamond) and a `lfs setstripe` command with stripe count > 1 is present.

**Feedback**: Provides tailored messages about the performance impact of wide striping for small-file workloads.

## Core Components

### Base Agent

All agents inherit from `BaseAgent` which provides a common interface:

```python
class BaseAgent(ABC):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
    
    @abstractmethod
    def run(self, context: JobContext) -> JobContext:
        pass
    
    def log_trace(self, context: JobContext, operation: str, details: Any = None):
        # Logs debugging information
        pass
```

### Adding a New Agent

To add a new agent:

1. Create a new class inheriting from `BaseAgent`.
2. Implement the `run` method.
3. Add it to the pipeline controller's agent list.

Example:
```python
from agentSlurm.agents.base_agent import BaseAgent
from agentSlurm.models.job_context import JobContext

class NewAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id="New Agent")
    
    def run(self, context: JobContext) -> JobContext:
        # Add your analysis logic here
        self.log_trace(context, "Processing new analysis")
        return context
```

### Pipeline Controller

The `PipelineController` orchestrates the execution of all agents in sequence. It handles the conditional execution of the LLM and Learning agents.

The `PipelineController` orchestrates the execution of all agents in sequence. It handles the conditional execution of the LLM and Learning agents.

### Implementation Details

#### Technologies
- **Language**: Python 3.8+
- **Data Validation**: `pydantic` for defining the `JobContext` and other data models, providing data validation and serialization.
- **Parsing**: Regular expressions for parsing SBATCH directives and commands.
- **LLM Integration**: OpenAI, Anthropic, Ollama, Hugging Face via LangChain.

#### Dependencies
- `pydantic`
- `PyYAML`
- `langchain`
- `openai`
- `anthropic`
- `huggingface_hub`

## Core Components

### Base Agent

All agents inherit from `BaseAgent` which provides a common interface:

```python
class BaseAgent(ABC):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @abstractmethod
    def run(self, context: JobContext) -> JobContext:
        pass

    def log_trace(self, context: JobContext, operation: str, details: Any = None):
        # Logs debugging information
        pass
```

### Adding a New Agent

To add a new agent:

1. Create a new class inheriting from `BaseAgent`.
2. Implement the `run` method.
3. Add it to the pipeline controller's agent list.

Example:
```python
from agentSlurm.agents.base_agent import BaseAgent
from agentSlurm.models.job_context import JobContext

class NewAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id="New Agent")

    def run(self, context: JobContext) -> JobContext:
        # Add your analysis logic here
        self.log_trace(context, "Processing new analysis")
        return context
```

### Pipeline Controller

The `PipelineController` orchestrates the execution of all agents in sequence. It handles the conditional execution of the LLM and Learning agents.

### Implementation Details

#### Technologies
- **Language**: Python 3.8+
- **Data Validation**: `pydantic` for defining the `JobContext` and other data models, providing data validation and serialization.
- **Parsing**: Regular expressions for parsing SBATCH directives and commands.
- **LLM Integration**: OpenAI, Anthropic, Ollama, Hugging Face via LangChain.

#### Dependencies
- `pydantic`
- `PyYAML`
- `langchain`
- `openai`
- `anthropic`
- `huggingface_hub`
- **Knowledge Base Format**: YAML for its human-readability and support for complex nested structures.
- **Data Structures**: `pydantic` for defining the `JobContext` and other data models, providing data validation and serialization.
## Development Conventions

### Code Structure
- All agents inherit from `BaseAgent` abstract class.
- Each agent implements a `run` method that takes a `JobContext` and returns an updated `JobContext`.
- The main application pipeline is controlled by the `PipelineController` which orchestrates the execution of agents.
- Model definitions in `models/` directory using Pydantic.
- Data flow through the `JobContext` object.
- Each agent enriches the context with its analysis.

### Testing

Traceability is paramount. The system includes structured logging for debugging.

#### Structured Logging

*   Every action taken by an agent will generate a structured log entry.
*   Each log entry will contain the `agent_id`, the specific function being executed, its inputs, and its outputs.
*   This allows for complete reconstruction of the analysis pipeline for any given script, which is essential for debugging.

## Development Workflow

### Setting Up the Environment

1. Install dependencies: `pip install -r requirements.txt`
2. Install the package in editable mode: `pip install -e .`

### Running the Analyzer

```bash
# As a CLI command (if installed)
agentslurm your_script.slurm --profile Medium

# With LLM integration
agentslurm your_script.slurm --use-llm --llm-provider openai --api-key YOUR_KEY
```

### Code Conventions

- Use Pydantic models for data validation.
- Follow the agent pattern for modularity.
- Log trace information for debugging.
- Use severity levels (INFO, WARNING, ERROR) appropriately.
- Tailor messages to different user experience levels.
- Implement proper error handling.

### Knowledge Base Format

The Knowledge Base (KB) is the brain of the agentic system. It is a centralized, version-controlled repository of rules, heuristics, and patterns that the analysis agents use to evaluate job scripts. It is explicitly separated from the application logic to allow for easy updates, versioning, and domain-specific customization.

#### Structure

The KB will be structured using a human-readable format like YAML, organized into distinct sections corresponding to the analysis agents.

```yaml
version: 1.0.0

slurm_rules:
  - rule_id: SLURM-001
    description: "Detects if total CPUs requested via --ntasks and --cpus-per-task are inconsistent."
    ...

lustre_rules:
  - rule_id: LUSTRE-001
    description: "Detects if a large file I/O workflow is missing an explicit 'lfs setstripe' command."
    ...

workflow_patterns:
  - workflow_id: WF-BIO-001
    name: "Variant Calling"
    # A sequence of executables that strongly implies this workflow
    command_sequence: ["bwa", "samtools sort", "gatk HaplotypeCaller"]
    ...

# ... and so on for other agents
```

#### Rule Definition Format

Each rule within the KB will have a detailed structure to ensure clarity, traceability, and effective application by the agents.

```yaml
- rule_id: LUSTRE-002
  # Human-readable description for documentation and logging
  description: "Warns when a many-small-files workflow uses wide striping."
  
  # The agent responsible for this rule
  agent: "Lustre Agent"
  
  # Default severity level
  severity: "Warning"
  
  # Conditions for the rule to trigger. Can be a simple check or a complex boolean expression.
  trigger_conditions:
    - type: "workflow_inference"
      name: "RNA-Seq QC"
      confidence_threshold: 0.7
    - type: "lfs setstripe_check"
      stripe_count: "> 1"

  # Feedback messages tailored to user experience levels
  feedback:
    Basic:
      title: "Inefficient File Storage Setting"
      message: "Your script appears to be creating many small files. Using 'lfs setstripe -c >1' can slow down the filesystem. For this type of job, it's best to let the system use the default setting or explicitly set 'lfs setstripe -c 1'."
    Medium:
      title: "Suboptimal Lustre Striping for Small Files"
      message: "This workflow seems to be generating many small files (e.g., QC reports). Wide striping (stripe count > 1) creates unnecessary metadata overhead for small files. Consider setting 'lfs setstripe -c 1' on your output directory to improve I/O efficiency and reduce load on the MDS."
    Advanced:
      title: "Potential MDS Contention due to Wide Striping on Small-File Workflow"
      message: "The inferred small-file I/O pattern of this workflow combined with a wide stripe setting may lead to excessive metadata operations and potential MDS contention. Recommend setting a stripe count of 1 for the output directory to optimize for this I/O profile."

  # Link to more detailed documentation
  documentation_url: "/docs/io_optimization/lustre_striping.md#small-files"
