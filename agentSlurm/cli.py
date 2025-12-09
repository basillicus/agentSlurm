#!/usr/bin/env python3
"""
Command-line interface for the Agentic Slurm Analyzer MVP.
"""

import argparse
import sys
from pathlib import Path
import os

from agentSlurm.pipeline_controller import PipelineController
from agentSlurm.models.job_context import UserProfile


def main():
    parser = argparse.ArgumentParser(description='Agentic Slurm Analyzer - MVP')
    parser.add_argument('script_path', type=str, help='Path to the SLURM script to analyze')
    parser.add_argument('--profile', type=str, default='Medium', 
                       choices=['Basic', 'Medium', 'Advanced'],
                       help='User experience level (Basic, Medium, Advanced)')
    parser.add_argument('--use-llm', action='store_true',
                       help='Use LLM for deeper analysis (requires API key)')
    parser.add_argument('--llm-provider', type=str, default='openai',
                       choices=['openai', 'anthropic', 'ollama', 'huggingface'],
                       help='LLM provider to use')
    parser.add_argument('--llm-model', type=str, default='gpt-3.5-turbo',
                       help='LLM model to use')
    parser.add_argument('--api-key', type=str, help='API key for LLM provider')
    parser.add_argument('--base-url', type=str, help='Base URL for LLM provider (for Ollama, Hugging Face custom endpoints)')
    parser.add_argument('--export-rules', type=str, help='Export learned rules to this file')
    parser.add_argument('--output-file', type=str, help='Path to save the analysis report in Markdown format')
    parser.add_argument('--focus-on', type=str, help='A comma-separated list of categories to focus on (e.g., LUSTRE,PERFORMANCE)')
    
    args = parser.parse_args()

    # Load API key from environment variables if not provided
    if args.use_llm and not args.api_key:
        if args.llm_provider == 'huggingface':
            args.api_key = os.environ.get('HF_TOKEN')
        elif args.llm_provider == 'openai':
            args.api_key = os.environ.get('OPENAI_API_KEY')
        elif args.llm_provider == 'anthropic':
            args.api_key = os.environ.get('ANTHROPIC_API_KEY')
    
    # Validate script file exists
    script_path = Path(args.script_path)
    if not script_path.exists():
        print(f"Error: Script file '{args.script_path}' does not exist.")
        sys.exit(1)
    
    # Read the script content
    try:
        with open(script_path, 'r') as f:
            script_content = f.read()
    except Exception as e:
        print(f"Error reading script file: {e}")
        sys.exit(1)
    
    # Convert profile string to enum
    try:
        user_profile = UserProfile(args.profile)
    except ValueError:
        print(f"Error: Invalid profile '{args.profile}'. Must be Basic, Medium, or Advanced.")
        sys.exit(1)
    
    focus_on = [c.strip().upper() for c in args.focus_on.split(',')] if args.focus_on else []

    # Create and run the pipeline
    llm_config = {
        'llm_provider': args.llm_provider,
        'model': args.llm_model,
        'api_key': args.api_key,
        'base_url': args.base_url
    }
    
    try:
        controller = PipelineController(
            user_profile=user_profile,
            use_llm=args.use_llm,
            llm_config=llm_config,
            focus_on=focus_on
        )
        context = controller.run_pipeline(script_content, str(script_path))
        
        # Get the report content
        report_content = ""
        if context.responses:
            report_content = context.responses[0]['content']
        else:
            report_content = "No analysis report generated."
    except Exception as e:
        print(f"\nError during analysis pipeline execution: {e}")
        sys.exit(1)

    # Print the final report
    print("\n" + report_content)

    # Save the report to a file if specified
    if args.output_file:
        try:
            with open(args.output_file, 'w') as f:
                f.write(report_content)
            print(f"\nReport saved to: {args.output_file}")
        except Exception as e:
            print(f"\nError saving report to file: {e}")
    
    # Export learned rules if LLM was used and export path specified
    if args.use_llm and args.export_rules:
        # Find the LLM agent to export its learned rules
        for agent in controller.agents:
            if hasattr(agent, 'export_learned_rules_for_kb'):
                agent.export_learned_rules_for_kb(args.export_rules)
                print(f"\nLearned rules exported to: {args.export_rules}")


if __name__ == "__main__":
    main()