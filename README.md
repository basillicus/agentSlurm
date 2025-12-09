# AgentSlurm: Agentic SLURM Job Script Analyzer

AgentSlurm is an intelligent, modular, and adaptive agentic AI system analyzer for SLURM job scripts in High-Performance Computing (HPC) environments. It identifies potential pitfalls, misconfigurations, and optimization opportunities, with a particular focus on Lustre filesystem performance, providing tailored feedback to users.

## Key Benefits

-   **For Users**: Faster job execution, better resource allocation, improved HPC understanding.
-   **For Sysadmins**: Reduced support load, proactive issue detection.
-   **For HPC Systems**: Higher throughput, efficient resource utilization.

## Installation

### Prerequisites
- Python 3.8+
- [Conda](https://docs.conda.io/en/latest/miniconda.html) (recommended) or pip

### Steps

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/basillicus/agentSlurm.git
    cd agentSlurm
    ```

2.  **Create and activate a conda environment (recommended):**
    ```bash
    conda create -n agentslurm-env python=3.9 # Or your preferred Python version
    conda activate agentslurm-env
    ```

3.  **Install dependencies:**
    ```bash
    pip install -e .
    ```

## Quick Start

Analyze a SLURM script:

```bash
agentslurm your_script.slurm
```

Example:
```bash
agentslurm agentSlurm/llm_test_script.slurm
```

For more options, including LLM integration and user profiles:
```bash
agentslurm --help
```

## Features

- **Lustre I/O Analysis**: Detects missing or suboptimal Lustre striping configurations
  - LUSTRE-001: Warns when large-file tools lack `lfs setstripe` configuration
  - LUSTRE-002: Warns when small-file tools use wide striping
- **LLM Integration**: Optional deep analysis using OpenAI, Anthropic, Ollama, or Hugging Face models
- **User Profiles**: Tailored feedback for Basic, Medium, or Advanced HPC users
- **Learning System**: Converts LLM insights into deterministic rules for future analysis
- **Customizable Focus**: Option to focus analysis on specific categories (e.g., LUSTRE, PERFORMANCE)

## Documentation

-   **User Guide**: Learn how to use AgentSlurm and interpret its reports.
    [docs/user_guide.md](docs/user_guide.md)
-   **Developer Guide**: Understand the architecture, contribute, and extend the system.
    [docs/developer_guide.md](docs/developer_guide.md)

---
*This README provides a high-level overview. For detailed information, please refer to the comprehensive User and Developer Guides.*
