#!/usr/bin/env python3
"""
Debug script for LLM response parsing in Agent Slurm.

This script helps diagnose issues with LLM response parsing by running
the parsing logic separately.
"""

import json
import sys
from pathlib import Path

# Import the LLM agent to test its parsing method
from agentSlurm.agents.llm_agent import LLMAgent
from agentSlurm.models.job_context import UserProfile


def test_response_parsing():
    """Test the response parsing logic with sample data."""

    # Sample responses that might come from LLM
    sample_responses = [
        # Case 1: Proper JSON in code block
        """```json
{
    "findings": [
        {
            "rule_id": "LLM-001",
            "severity": "WARNING", 
            "title": "Test Issue 1",
            "message": "This is a test warning",
            "line_number": 10
        }
    ]
}
```""",
        # Case 2: JSON without code block
        """{
    "findings": [
        {
            "rule_id": "LLM-002",
            "severity": "INFO",
            "title": "Test Info 1", 
            "message": "This is a test info"
        }
    ]
}""",
        # Case 3: JSON with incomplete code block (like in the example)
        """```json
{
  "findings": [
    {
      "rule_id": "LLM-001",
      "severity": "WARNING",
      "title": "Potential overwrite and missing existence check for cp",
      "message": "The command `cp /path/to/reference.fa ./` could overwrite an existing file without warning..."
    }
  ]
}
""",
        # Case 4: Mixed content with JSON
        """Here's my analysis:
```json
{
  "findings": [
    {
      "rule_id": "LLM-003",
      "severity": "ERROR",
      "title": "Critical Issue",
      "message": "A critical issue was found"
    }
  ]
}
```
Additional comments after the JSON.
""",
    ]

    # Create an LLM agent instance
    agent = LLMAgent(llm_provider="openai", model="gpt-3.5-turbo", api_key="test")

    for i, response in enumerate(sample_responses, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Input response: {response[:200]}...")

        # Test parsing
        findings = agent._parse_llm_response(response, UserProfile.ADVANCED)

        print(f"Number of findings: {len(findings)}")
        for j, finding in enumerate(findings, 1):
            print(
                f"  Finding {j}: {finding.title} [{finding.severity}] - {finding.rule_id}"
            )
            print(f"    Message: {finding.message[:100]}...")


def parse_real_response():
    """Parse an actual response example from the user's output."""

    # Example from the user's output that shows the issue
    problematic_response = """```json
{
  "findings": [
    {
      "rule_id": "LLM-001",
      "severity": "WARNING",
      "title": "Potential overwrite and missing existence check for cp",
      "message": "The command `cp /path/to/reference.fa ./` could overwrite an existing file without warning. Consider adding an existence check or using a safer copy method to prevent accidental data loss.",
      "line_number": 10
    }
  ]
}
"""

    print("Testing parsing of real problematic response...")
    print(f"Response: {problematic_response[:200]}...")

    agent = LLMAgent(llm_provider="openai", model="gpt-3.5-turbo", api_key="test")
    findings = agent._parse_llm_response(problematic_response, UserProfile.ADVANCED)

    print(f"Findings extracted: {len(findings)}")
    for finding in findings:
        print(f"  - {finding.title} [{finding.severity}]")


if __name__ == "__main__":
    print("Testing LLM response parsing...")
    test_response_parsing()
    print("\n" + "=" * 50)
    parse_real_response()

