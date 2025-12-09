# AgentSlurm Codebase Understanding Guide

## Overview

AgentSlurm is an intelligent analyzer for SLURM job scripts in High-Performance Computing (HPC) environments. The system combines deterministic rule-based analysis with large language model (LLM) powered insights to provide comprehensive feedback on SLURM scripts, particularly focusing on Lustre filesystem optimization.

## Architecture

### Agent-Based Design Pattern

AgentSlurm implements a modular, agent-based architecture where each component has a specific responsibility. This design follows the Single Responsibility Principle and enables individual components to be developed, tested, and updated in isolation.

The system operates as a data processing pipeline where a `JobContext` object is created for each script and passed sequentially through various agents. Each agent enriches this object with its analysis, logs, and confidence scores.

### Data Flow Architecture

The system implements a data-driven pipeline:
1. A `JobContext` object is created with the raw script content
2. The context is passed through agents in sequence
3. Each agent analyzes the context and adds findings
4. The final report is generated from the enriched context

## Core Components

### 1. JobContext Model

The `JobContext` is the central data structure that flows through the pipeline:

```python
class JobContext(BaseModel):
    # Input data
    raw_script: str                  # Original script content
    user_profile: UserProfile       # User experience level (Basic/Medium/Advanced)

    # Parsed data
    parsed_elements: List[ParsedElement]  # Structured representation of script
    user_commands: List[UserCommand]      # Commands from script comments

    # Analysis results
    inferred_workflow: Optional[WorkflowInference]  # Detected workflow type
    findings: List[Finding]            # Issues/suggestions found by agents
    responses: List[Dict[str, Any]]    # Direct responses to user commands

    # Tracing and debugging
    trace_log: List[Dict[str, Any]]    # Detailed execution trace
    script_path: Optional[str]         # Path to the script file
```

### 2. BaseAgent Abstract Class

All agents inherit from the `BaseAgent` abstract class which provides a common interface:

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

### 3. Core Agents

#### Parser Agent
The Parser Agent converts raw SLURM scripts into structured elements. It extracts:
- SBATCH directives using regex pattern matching
- Commands (identifying tool commands and Lustre commands)
- Special comment patterns for in-script communication

Key functionality:
- Identifies tool commands for applications like bwa, gatk, samtools (large-file tools)
- Identifies Lustre commands like lfs setstripe
- Extracts #SBATCH directives
- Stores parsed elements with line numbers for precise reporting

#### Lustre Agent
The primary analysis agent that implements Lustre I/O optimization rules:

**LUSTRE-001 Rule**: Detects if large-file workflows are missing explicit `lfs setstripe` configuration
- Triggers when tools like bwa, gatk, samtools, vasp are found without lfs setstripe commands
- Provides tailored feedback for different user experience levels

**LUSTRE-002 Rule**: Warns when many-small-files workflows use wide striping
- Triggers when tools like fastqc, multiqc, blastn are found with stripe count > 1
- Provides appropriate recommendations for small-file workflows

#### LLM Agent (Optional)
Performs deeper analysis using Large Language Models when enabled:
- Supports multiple providers: OpenAI, Anthropic, Ollama, Hugging Face
- Analyzes patterns not caught by rule-based agents
- Provides more nuanced insights for complex scripts

#### Learning Agent (Optional)
Converts LLM insights into deterministic rules:
- Processes findings from LLM analysis
- Creates new rules that can be applied in future deterministic analyses
- Integrates with the KnowledgeBaseUpdater for persistent learning

#### Synthesis Agent
Consolidates all findings into a user-friendly report:
- Collects findings from all agents
- Formats the analysis results appropriately
- Generates the final response with feedback tailored to the user's profile

### 4. Pipeline Controller

The `PipelineController` orchestrates the execution of all agents in sequence:

```python
class PipelineController:
    def __init__(self, user_profile, use_llm, llm_config, focus_on):
        # Initialize agents based on configuration
        # LLM and Learning agents only added if use_llm=True
        self.agents = [ParserAgent(), LustreAgent()]
        if use_llm:
            llm_agent = LLMAgent(**llm_config)
            self.agents.append(llm_agent)
            self.agents.append(LearningAgent())
        self.agents.append(SynthesisAgent(llm_agent=llm_agent))
    
    def run_pipeline(self, script_content, script_path=None):
        # Create initial context
        context = JobContext(raw_script=script_content, user_profile=self.user_profile)
        
        # Run each agent in sequence
        for agent in self.agents:
            context = agent.run(context)
        
        return context
```

## Data Models

### ParsedElement
Represents a single parsed element from the script:
- `element_type`: 'SBATCH', 'COMMAND', 'TOOL_COMMAND', 'LUSTRE_COMMAND'
- `key`, `value`: For SBATCH directives
- `line_number`: Original line number for reporting
- `raw_line`: Original line text

### Finding
Represents an issue or suggestion found by an agent:
- `agent_id`: Which agent generated the finding
- `rule_id`: Unique identifier for the rule (e.g., "LUSTRE-001")
- `severity`: INFO, WARNING, or ERROR
- `title`, `message`: User-facing description
- `line_number`: Specific line where issue occurs
- `category`: Classification for filtering (e.g., "LUSTRE")

## Agent Communication Pattern

The system implements a sequential pipeline where each agent receives the `JobContext`, modifies it, and passes it to the next agent:

```
[SLURM Script] -> [Parser Agent] -> [Lustre Agent] -> [LLM Agent (optional)] -> 
[Learning Agent (optional)] -> [Synthesis Agent] -> [Report]
```

Each agent only needs to know about the `JobContext` structure and how its specific responsibilities contribute to the overall analysis.

## LLM Integration

The system supports multiple LLM providers through a unified interface:

### Supported Providers:
- **OpenAI**: GPT models for sophisticated analysis
- **Anthropic**: Claude models for nuanced understanding
- **Ollama**: Local models for privacy-conscious environments
- **Hugging Face**: Access to various open-source models

### LLM Configuration:
The system can be configured with different providers and models, with fallback to environment variables for API keys.

## Learning System

The knowledge learning mechanism works in two phases:
1. **Insight Generation**: LLM identifies patterns and insights during analysis
2. **Rule Conversion**: Learning agent converts insights into structured rules

The `KnowledgeBaseUpdater` class handles storing learned rules in a YAML file in the user's home directory for future deterministic analysis.

## CLI Interface

The command-line interface provides various options:
- `--profile`: User experience level (Basic/Medium/Advanced)
- `--use-llm`: Enable deeper analysis with LLM
- `--llm-provider`: Choose from openai, anthropic, ollama, huggingface
- `--llm-model`: Specify the model to use
- `--api-key`: Provide API key for LLM providers
- `--export-rules`: Export learned rules to a file
- `--output-file`: Save report to a file
- `--focus-on`: Focus on specific categories (e.g., LUSTRE,PERFORMANCE)

## Design Patterns Used

### 1. Chain of Responsibility
The agent pipeline implements the Chain of Responsibility pattern where each agent processes the JobContext in sequence.

### 2. Strategy Pattern
The LLM integration uses Strategy pattern with different providers implementing the same interface.

### 3. Observer Pattern
The trace logging mechanism allows monitoring of agent execution without tightly coupling components.

## Key Algorithms

### Tool Detection
The system uses predefined sets of tools to identify different workload types:
- Large-file tools: bwa, gatk, samtools, vasp, star, hisat2, bowtie2
- Small-file tools: fastqc, multiqc, blastn, blastp, diamond

### Stripe Detection
Regex pattern matching to identify lfs setstripe commands and extract stripe count values for analysis.

## Error Handling

The system implements robust error handling:
- Input validation for script files
- Graceful degradation when LLM services are unavailable
- Comprehensive exception handling in each agent
- Detailed logging for debugging purposes

## Extensibility

The agent-based design makes the system highly extensible:

### Adding New Agents
To add a new agent:
1. Inherit from `BaseAgent` class
2. Implement the `run` method with the specific analysis logic
3. Add to the pipeline controller's agent list

### Adding New Rules
New rules can be added to existing agents by:
1. Extending the rules dictionary in the agent
2. Implementing detection logic
3. Adding appropriate feedback messages for all user profiles

### Adding New LLM Providers
New providers can be integrated by:
1. Extending the supported provider list
2. Implementing the provider-specific API calls
3. Adding validation for the new provider

## Testing Strategy

The system emphasizes traceability with structured logging and evaluation hooks. Each agent's decision is logged with:
- Unique trace ID
- Agent ID and operation
- Input and output details
- Confidence scores

## Performance Considerations

- The core rule-based analysis is fast and deterministic
- LLM integration is optional for deeper analysis when needed
- The system can process scripts efficiently without external dependencies
- Results are cached where appropriate to avoid redundant analysis

This architecture enables AgentSlurm to provide reliable, fast analysis for common issues while optionally leveraging LLMs for complex patterns, creating a hybrid system that balances performance with intelligent insights.