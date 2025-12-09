from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="agentSlurm",
    version="0.1.0",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "agentslurm=agentSlurm.cli:main",
        ],
    },
    author="HPC Team",
    description="Agentic Slurm Analyzer - MVP",
    python_requires=">=3.8",
)