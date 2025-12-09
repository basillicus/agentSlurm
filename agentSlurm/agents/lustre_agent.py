from typing import Dict, List
from agentSlurm.agents.base_agent import BaseAgent
from agentSlurm.models.job_context import JobContext, Finding, Severity, UserProfile


class LustreAgent(BaseAgent):
    """
    The Lustre Agent analyzes file I/O patterns and Lustre-specific commands
    to identify potential performance issues and configuration problems.
    """

    def __init__(self):
        super().__init__(agent_id="Lustre Agent")
        # Define tools commonly used with large files (should use striping)
        self.large_file_tools = {
            "bwa",
            "gatk",
            "samtools",
            "vasp",
            "star",
            "hisat2",
            "bowtie2",
        }
        # Define tools commonly used with small files (should not use wide striping)
        self.small_file_tools = {"fastqc", "multiqc", "blastn", "blastp", "diamond"}

        # Knowledge base of Lustre rules
        self.lustre_rules = {
            "LUSTRE-001": {
                "description": "Detects if a large-file workflow is missing an explicit 'lfs setstripe' command.",
                "agent": "Lustre Agent",
                "severity": Severity.WARNING,
                "feedback": self._get_feedback_for_lustre_001(),
            },
            "LUSTRE-002": {
                "description": "Warns when a many-small-files workflow uses wide striping.",
                "agent": "Lustre Agent",
                "severity": Severity.WARNING,
                "feedback": self._get_feedback_for_lustre_002(),
            },
        }

    def _get_feedback_for_lustre_001(self) -> Dict[UserProfile, Dict[str, str]]:
        """Get feedback messages for LUSTRE-001 rule."""
        return {
            UserProfile.BASIC: {
                "title": "Missing Lustre Striping Configuration",
                "message": "Your script appears to work with large files but doesn't specify Lustre striping. For better I/O performance on large files, consider adding an 'lfs setstripe' command to optimize how your data is distributed across Lustre storage servers.",
            },
            UserProfile.MEDIUM: {
                "title": "Missing Lustre Striping Configuration",
                "message": "This workflow appears to process large files (detected tools like bwa, gatk, etc.) without explicit Lustre striping configuration. For large-file I/O patterns, setting an appropriate stripe count and size using 'lfs setstripe' can significantly improve performance. Consider adding 'lfs setstripe -c [n] -s [size] [directory]' where appropriate.",
            },
            UserProfile.ADVANCED: {
                "title": "Suboptimal Lustre I/O Configuration",
                "message": "Large-file workflow detected without Lustre striping optimization. For optimal performance with tools like bwa/gatk, consider configuring striping with an appropriate stripe count and size. For example: 'lfs setstripe -c [n] -s [size] $OUTPUT_DIR' where n is the number of OSTs you want to stripe across and size is the stripe size (e.g., 16M, 64M).",
            },
        }

    def _get_feedback_for_lustre_002(self) -> Dict[UserProfile, Dict[str, str]]:
        """Get feedback messages for LUSTRE-002 rule."""
        return {
            UserProfile.BASIC: {
                "title": "Inefficient File Storage Setting",
                "message": "Your script appears to be creating many small files. Using 'lfs setstripe -c >1' can slow down the filesystem. For this type of job, it's best to let the system use the default setting or explicitly set 'lfs setstripe -c 1'.",
            },
            UserProfile.MEDIUM: {
                "title": "Suboptimal Lustre Striping for Small Files",
                "message": "This workflow seems to be generating many small files (e.g., QC reports). Wide striping (stripe count > 1) creates unnecessary metadata overhead for small files. Consider setting 'lfs setstripe -c 1' on your output directory to improve I/O efficiency and reduce load on the MDS.",
            },
            UserProfile.ADVANCED: {
                "title": "Potential MDS Contention due to Wide Striping on Small-File Workflow",
                "message": "The inferred small-file I/O pattern of this workflow combined with a wide stripe setting may lead to excessive metadata operations and potential MDS contention. Recommend setting a stripe count of 1 for the output directory to optimize for this I/O profile.",
            },
        }

    def run(self, context: JobContext) -> JobContext:
        """
        Analyze the context for Lustre-related issues.

        Args:
            context: The JobContext containing parsed elements and workflow info

        Returns:
            The updated JobContext with Lustre-related findings
        """
        self.log_trace(context, "Starting Lustre analysis")

        # Check if any large file tools are present in the script
        has_large_file_tools = False
        has_small_file_tools = False
        has_lfs_setstripe = False
        found_wide_striping_command = False # Initialize new flag
        lfs_setstripe_lines = []

        for element in context.parsed_elements:
            if element.element_type == "TOOL_COMMAND" and element.value is not None:
                command_text = element.value.lower()
                # Check for large file tools
                for tool in self.large_file_tools:
                    if tool in command_text:
                        has_large_file_tools = True
                        break
                # Check for small file tools
                for tool in self.small_file_tools:
                    if tool in command_text:
                        has_small_file_tools = True
                        break
            elif element.element_type == "LUSTRE_COMMAND":
                if element.value is not None and "setstripe" in element.value.lower():
                    has_lfs_setstripe = True
                    lfs_setstripe_lines.append(element.line_number)
                    
                    # Check if it's wide striping (stripe count > 1)
                    import re

                    stripe_match = re.search(r"-c\s+(\d+)", element.value)
                    if stripe_match:
                        try:
                            stripe_count = int(stripe_match.group(1))
                            if stripe_count > 1:
                                found_wide_striping_command = True
                        except ValueError:
                            pass # If we can't parse the stripe count, ignore

        # Apply rule LUSTRE-001: Missing lfs setstripe in large-file workflows
        if has_large_file_tools and not has_lfs_setstripe:
            rule_id = "LUSTRE-001"
            feedback = self.lustre_rules[rule_id]["feedback"][context.user_profile]

            finding = Finding(
                agent_id=self.agent_id,
                rule_id=rule_id,
                severity=self.lustre_rules[rule_id]["severity"],
                title=feedback["title"],
                message=feedback["message"],
                line_number=None,  # No specific line, it's a missing pattern
                category="LUSTRE",
            )
            context.findings.append(finding)

        # Apply rule LUSTRE-002: Wide striping in small-file workflows
        if has_small_file_tools and found_wide_striping_command: # Use the new flag here
            rule_id = "LUSTRE-002"
            feedback = self.lustre_rules[rule_id]["feedback"][context.user_profile]

            # We need to find the specific line number where the wide striping command occurred
            finding_line_number = None
            for element in context.parsed_elements:
                if element.element_type == "LUSTRE_COMMAND" and element.value is not None and "setstripe" in element.value.lower():
                    stripe_match = re.search(r"-c\s+(\d+)", element.value)
                    if stripe_match:
                        try:
                            stripe_count = int(stripe_match.group(1))
                            if stripe_count > 1:
                                finding_line_number = element.line_number
                                break
                        except ValueError:
                            pass

            finding = Finding(
                agent_id=self.agent_id,
                rule_id=rule_id,
                severity=self.lustre_rules[rule_id]["severity"],
                title=feedback["title"],
                message=feedback["message"],
                line_number=finding_line_number,
                category="LUSTRE",
            )
            context.findings.append(finding)

        self.log_trace(
            context,
            "Lustre analysis completed",
            {
                "large_file_tools_found": has_large_file_tools,
                "small_file_tools_found": has_small_file_tools,
                "lfs_setstripe_found": has_lfs_setstripe,
                "wide_striping_command_found": found_wide_striping_command, # Log the new flag
                "findings_added": len(context.findings),
            },
        )

        return context

