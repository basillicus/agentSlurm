# AgentSlurm User Guide

## Overview

AgentSlurm is an intelligent analyzer for SLURM job scripts that helps users optimize their HPC jobs, particularly focusing on Lustre filesystem performance. This tool automatically reviews your SLURM scripts and provides actionable feedback to improve performance and efficiency.

## Getting Started

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/basillicus/agentSlurm.git
    cd agentSlurm
    ```

2.  **Create and activate a conda environment (recommended):**
    ```bash
    conda create -n agentslurm-env python=3.9   # Or your preferred Python version
    conda activate agentslurm-env
    ```

3.  **Install dependencies:**
    ```bash
    pip install -e .
    ```

4.  **Verify installation:**
    ```bash
    agentslurm --help
    ```

### Running the Analyzer

Basic usage:
```bash
agentslurm /path/to/your/slurm_script.slurm
```

With user profile specification:
```bash
agentslurm /path/to/your/slurm_script.slurm --profile Medium
```

Available user profiles:
- `Basic`: Simple explanations for newcomers to HPC
- `Medium`: Balanced explanations for regular users (default)
- `Advanced`: Technical details for experienced HPC users

## Command Line Options

### Basic Options
- `script_path`: Path to the SLURM script to analyze (required)
- `--profile`: User experience level (Basic, Medium, Advanced) [default: Medium]
- `--output-file`: Path to save the analysis report in Markdown format
- `--focus-on`: Comma-separated list of categories to focus on (e.g., LUSTRE,PERFORMANCE)

### LLM Options
- `--use-llm`: Enable LLM for deeper analysis
- `--llm-provider`: LLM provider to use (openai, anthropic, ollama, huggingface) [default: openai]
- `--llm-model`: Model to use [default: gpt-3.5-turbo]
- `--api-key`: API key for LLM provider (not needed for Ollama); if not provided, the system will try environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY, or HF_TOKEN respectively)
- `--base-url`: Base URL for LLM provider (for Ollama, Hugging Face custom endpoints)
- `--export-rules`: Export learned rules to this file (only with LLM analysis)

## Advanced Usage with LLM Integration

### OpenAI Integration
```bash
# Basic OpenAI analysis with API key
agentslurm /path/to/your/script.slurm --use-llm --llm-provider openai --llm-model gpt-3.5-turbo --api-key YOUR_API_KEY

# Or using environment variable (set OPENAI_API_KEY=your_key in your environment)
agentslurm /path/to/your/script.slurm --use-llm --llm-provider openai --llm-model gpt-3.5-turbo
```

### Anthropic Integration
```bash
# Using Claude models with API key
agentslurm /path/to/your/script.slurm --use-llm --llm-provider anthropic --llm-model claude-3-sonnet --api-key YOUR_API_KEY

# Or using environment variable (set ANTHROPIC_API_KEY=your_key in your environment)
agentslurm /path/to/your/script.slurm --use-llm --llm-provider anthropic --llm-model claude-3-sonnet
```

### Ollama Integration (Local Models)
```bash
# Using locally running models (make sure Ollama is installed and running: `ollama serve`)
# No API key needed for local models
agentslurm /path/to/your/script.slurm --use-llm --llm-provider ollama --llm-model llama2

# With custom Ollama server URL
agentslurm /path/to/your/script.slurm --use-llm --llm-provider ollama --llm-model mistral --base-url http://localhost:11434/v1
```

### Hugging Face Integration
```bash
# Using Hugging Face models with API key
agentslurm /path/to/your/script.slurm --use-llm --llm-provider huggingface --llm-model microsoft/DialoGPT-medium --api-key YOUR_HF_API_KEY

# With custom Hugging Face endpoint
agentslurm /path/to/your/script.slurm --use-llm --llm-provider huggingface --base-url https://your-endpoint.hf.space --api-key YOUR_HF_API_KEY
```

### Exporting Learned Rules
After running LLM analysis, you can export newly learned rules:

```bash
agentslurm /path/to/your/script.slurm --use-llm --llm-provider openai --api-key YOUR_API_KEY --export-rules learned_rules.yaml
```

## Understanding the Output

### Report Format

The analyzer produces a structured report with:

1. **Issues Found**: Problems detected in your script with severity indicators:
   - ⚠️ **Warning**: Something that could cause performance issues
   - ❌ **Error**: Something that could cause job failure
   - ℹ️ **Info**: Helpful information about your script

2. **Analysis Summary**: Key information about what was detected in your script

### Example Output

```
Agentic Slurm Analyzer - Analysis Report
=======================================

Issues Found:
-------------
1. ⚠️ Missing Lustre Striping Configuration
   This workflow appears to process large files (detected tools like bwa, gatk, etc.) without explicit Lustre striping configuration. For large-file I/O patterns, setting an appropriate stripe count and size using 'lfs setstripe' can significantly improve performance. Consider adding 'lfs setstripe -c [n] -s [size] [directory]' where appropriate.

Analysis Summary:
-----------------
• Total findings: 1
• User profile: Medium
• Tools detected: bwa, samtools
```

## Current Analysis Features

### 1. Lustre I/O Analysis

#### LUSTRE-001: Missing Lustre Striping for Large Files

**Detection**: When the script includes tools commonly used for processing large files (bwa, gatk, samtools, vasp, star, hisat2, bowtie2) but no `lfs setstripe` command is present.

**Recommendation**: Add an appropriate `lfs setstripe` command:
```bash
# For large files, spread across multiple OSTs
lfs setstripe -c 4 -s 64M $OUTPUT_DIR
```

#### LUSTRE-002: Inappropriate Wide Striping for Small Files

**Detection**: When the script includes tools commonly used for processing many small files (fastqc, multiqc, blastn, blastp, diamond) and a `lfs setstripe` command with stripe count > 1 is present.

**Recommendation**: Use single stripe for small files:
```bash
# For many small files, use single stripe
lfs setstripe -c 1 $OUTPUT_DIR
```

## LLM Provider Setup

### OpenAI
1. Create an account at [OpenAI Platform](https://platform.openai.com/)
2. Generate an API key in the dashboard
3. Use the API key with the `--api-key` option or set the `OPENAI_API_KEY` environment variable

### Anthropic
1. Create an account at [Anthropic](https://www.anthropic.com/)
2. Generate an API key
3. Use the API key with the `--api-key` option or set the `ANTHROPIC_API_KEY` environment variable

### Ollama (Local Models)
1. Install Ollama from [ollama.ai](https://ollama.ai/)
2. Pull a model: `ollama pull llama2`
3. Start the Ollama server: `ollama serve`
4. Run Agent Slurm without an API key

### Hugging Face
1. Create an account at [Hugging Face](https://huggingface.co/) and get an API key
2. Use the API key with the `--api-key` option or set the `HF_TOKEN` environment variable

## Security Considerations

- API keys should be treated as sensitive information
- Don't hardcode API keys in script files
- Consider using environment variables or secure credential management in production environments
- The system only processes the SLURM script content and doesn't store your API keys
- API keys can be provided via command line or environment variables

## Best Practices

- **Analyze Your Scripts**: Run AgentSlurm before submitting large or important jobs
- **Check Lustre I/O**: Apply Lustre striping recommendations for better performance
- **Use Appropriate User Profiles**: Select the profile level that matches your HPC expertise
- **Enable LLM Integration**: For complex scripts, use LLM analysis to get deeper insights

## Getting More Help

If you encounter issues or have questions:
1. Run your script through AgentSlurm with different user profiles
2. Check your HPC center's documentation for Lustre guidelines
3. Consult with system administrators for site-specific recommendations
