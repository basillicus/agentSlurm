#!/usr/bin/env python3
"""
Test harness for the Parser Agent using Parsimonious.
"""

import unittest
from agentSlurm.agents.parser_agent import ParserAgent
from agentSlurm.models.job_context import JobContext

class TestParserAgent(unittest.TestCase):

    def setUp(self):
        self.parser = ParserAgent()

    def test_basic_parsing(self):
        """Test parsing of a standard Slurm script."""
        script = """#!/bin/bash
#SBATCH --job-name=test_job
#SBATCH --nodes=4
#SBATCH --time=02:00:00

# Load modules
module load python/3.8

# Run script
python myscript.py
"""
        context = JobContext(raw_script=script)
        context = self.parser.run(context)

        # Check SBATCH directives
        sbatch_elements = [e for e in context.parsed_elements if e.element_type == "SBATCH"]
        self.assertEqual(len(sbatch_elements), 3)
        self.assertEqual(sbatch_elements[0].key, "--job-name")
        self.assertEqual(sbatch_elements[0].value, "test_job")
        
        # Check commands
        commands = [e for e in context.parsed_elements if e.element_type == "COMMAND"]
        self.assertTrue(any("module load python/3.8" in c.value for c in commands))
        self.assertTrue(any("python myscript.py" in c.value for c in commands))

    def test_agent_comments(self):
        """Test parsing of special Agent SLURM comments."""
        script = """#!/bin/bash
#SBATCH --nodes=1
# Agent SLURM: Optimize this section
srun ./app
"""
        context = JobContext(raw_script=script)
        context = self.parser.run(context)

        self.assertEqual(len(context.user_commands), 1)
        self.assertEqual(context.user_commands[0].message, "Optimize this section")

    def test_complex_sbatch(self):
        """Test parsing of complex SBATCH directives."""
        script = """#!/bin/bash
#SBATCH -J myjob
#SBATCH --mem=4G # This is a comment
#SBATCH --exclusive
"""
        context = JobContext(raw_script=script)
        context = self.parser.run(context)
        
        sbatch_elements = [e for e in context.parsed_elements if e.element_type == "SBATCH"]
        
        # -J myjob
        self.assertEqual(sbatch_elements[0].key, "-J")
        self.assertEqual(sbatch_elements[0].value, "myjob")
        
        # --mem=4G
        self.assertEqual(sbatch_elements[1].key, "--mem")
        self.assertEqual(sbatch_elements[1].value, "4G")
        
        # --exclusive (flag)
        self.assertEqual(sbatch_elements[2].key, "--exclusive")
        self.assertIsNone(sbatch_elements[2].value)

    def test_tool_detection(self):
        """Test specific tool command detection."""
        script = """
lfs setstripe -c 1 file.dat
bwa mem ref.fa reads.fq
"""
        context = JobContext(raw_script=script)
        context = self.parser.run(context)
        
        lustre_cmds = [e for e in context.parsed_elements if e.element_type == "LUSTRE_COMMAND"]
        tool_cmds = [e for e in context.parsed_elements if e.element_type == "TOOL_COMMAND"]
        
        self.assertEqual(len(lustre_cmds), 1)
        self.assertEqual(len(tool_cmds), 1)
        self.assertIn("lfs setstripe", lustre_cmds[0].value)
        self.assertIn("bwa mem", tool_cmds[0].value)

    def test_fallback_mechanism(self):
        """Test that the parser falls back gracefully on weird syntax."""
        # Using characters or patterns that might strictly violate a simple grammar 
        # but should be caught by fallback or loose parsing.
        # Intentionally malformed or tricky input
        script = """
#SBATCH --weird-syntax::::value
Some crazy binary looking string \x00
"""
        context = JobContext(raw_script=script)
        # This shouldn't crash
        try:
            context = self.parser.run(context)
            # If fallback worked, we might get some parsed elements or at least no crash
            # The regex fallback is quite permissive
        except Exception as e:
            self.fail(f"Parser crashed on tricky input: {e}")

if __name__ == '__main__':
    unittest.main()
