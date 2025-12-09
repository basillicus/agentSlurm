from agentSlurm.agents.base_agent import BaseAgent
from agentSlurm.agents.llm_agent import LLMAgent
from agentSlurm.models.job_context import JobContext, UserProfile, Finding
from agentSlurm.utils.knowledge_base_updater import integrate_learned_rules_from_llm_agent
from typing import Optional, List, Dict


class SynthesisAgent(BaseAgent):
    """
    The Synthesis Agent consolidates all findings and generates the final report.
    """

    def __init__(self, llm_agent: Optional[BaseAgent] = None, focus_on: Optional[List[str]] = None):
        super().__init__(agent_id="Synthesis Agent")
        self.llm_agent = llm_agent
        self.focus_on = focus_on or []

    def run(self, context: JobContext) -> JobContext:
        """
        Generate the final report from all findings.
        
        Args:
            context: The JobContext containing all findings
            
        Returns:
            The updated JobContext with the report
        """
        self.log_trace(
            context, "Starting synthesis", {"total_findings": len(context.findings)}
        )

        if self.focus_on:
            from agentSlurm.models.job_context import Severity
            context.findings.sort(
                key=lambda f: (f.category not in self.focus_on, f.severity != Severity.ERROR, f.severity != Severity.WARNING, f.severity != Severity.INFO)
            )

        report_lines = ["Agentic Slurm Analyzer - Analysis Report", "=" * 45, ""]

        if context.user_profile == UserProfile.BASIC and context.findings:
            report_lines.extend(self._generate_basic_report(context))
        elif context.findings:
            report_lines.extend(self._generate_default_report(context))
        else:
            report_lines.append("✅ No issues detected with your SLURM script!")
            report_lines.append("")
        
        # Common summary for all profiles
        report_lines.append("Analysis Summary:")
        report_lines.append("-" * 17)
        report_lines.append(f"• Total findings: {len(context.findings)}")
        report_lines.append(f"• User profile: {context.user_profile.value}")
        report_lines.append(f"• Tools detected: {self._extract_tools(context)}")

        if any(f.agent_id == "LLM Agent" for f in context.findings):
            report_lines.append(
                f"• LLM-powered analysis: Some findings based on AI insights"
            )
            report_lines.append(
                f"• Knowledge base learning: New patterns identified for future rule creation"
            )

        context.responses.append(
            {"type": "analysis_report", "content": "\n".join(report_lines)}
        )

        self.log_trace(context, "Synthesis completed")

        return context

    def _generate_default_report(self, context: JobContext) -> List[str]:
        """Generate the default report for Medium and Advanced profiles."""
        report_lines = []
        report_lines.append("Issues Found:")
        report_lines.append("-" * 15)

        for i, finding in enumerate(context.findings, 1):
            severity_symbol = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}.get(
                finding.severity.value, "•"
            )

            line_ref = f" (line {finding.line_number})" if finding.line_number else ""
            report_lines.append(f"{i}. {severity_symbol} {finding.title}{line_ref}")
            report_lines.append(f"   {finding.message}")
            report_lines.append("")

        if self.llm_agent:
            from agentSlurm.models.job_context import UserProfile, Severity

            findings_for_correction = []
            if context.user_profile == UserProfile.ADVANCED:
                findings_for_correction = list(enumerate(context.findings, 1))
            elif context.user_profile == UserProfile.MEDIUM:
                for i, f in enumerate(context.findings, 1):
                    if f.severity in [Severity.ERROR, Severity.WARNING] or (
                        f.agent_id == "Lustre Agent" and f.severity == Severity.INFO
                    ):
                        findings_for_correction.append((i, f))

            if findings_for_correction:
                # Ensure llm_agent is an actual LLMAgent instance before calling its specific method
                if isinstance(self.llm_agent, LLMAgent):
                    correction_context = context.copy(deep=True)
                    correction_context.findings = [f for i, f in findings_for_correction]
                    corrected_script = self.llm_agent.generate_corrected_script(
                        correction_context, findings_for_correction
                    )
                    if corrected_script:
                        report_lines.append("Corrected Script:")
                        report_lines.append("-" * 17)
                        report_lines.append("```bash")
                        report_lines.append(corrected_script)
                        report_lines.append("```")
                        report_lines.append("")
        return report_lines

    def _generate_basic_report(self, context: JobContext) -> List[str]:
        """Generate a simplified, educational report for the Basic profile."""
        from agentSlurm.models.job_context import Severity

        report_lines = []

        critical_findings = [
            f for f in context.findings if f.severity == Severity.ERROR
        ]
        non_critical_findings = [
            f for f in context.findings if f.severity != Severity.ERROR
        ]

        # Sort non-critical findings by severity (warnings first)
        non_critical_findings.sort(
            key=lambda f: (f.severity != Severity.WARNING, f.severity != Severity.INFO)
        )

        # Limit to top 3 non-critical findings
        selected_findings = critical_findings + non_critical_findings[:3]

        # Group findings by category
        grouped_findings: Dict[str, List[Finding]] = {}
        for finding in selected_findings:
            category = finding.category or "OTHER"
            if category not in grouped_findings:
                grouped_findings[category] = []
            grouped_findings[category].append(finding)

        report_lines.append("Key Recommendations:")
        report_lines.append("-" * 20)

        for category, findings in grouped_findings.items():
            report_lines.append(f"### {category.replace('_', ' ').title()}\n")
            report_lines.append(self._get_educational_description(category) + "\n")
            for finding in findings:
                severity_symbol = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}.get(
                    finding.severity.value, "•"
                )
                line_ref = (
                    f" (line {finding.line_number})" if finding.line_number else ""
                )
                report_lines.append(
                    f"* **{finding.title}{line_ref}**: {finding.message}"
                )
            report_lines.append("")

        if self.llm_agent and selected_findings:
            # Ensure llm_agent is an actual LLMAgent instance before calling its specific method
            if isinstance(self.llm_agent, LLMAgent):
                findings_for_correction = [
                    (i, f)
                    for i, f in enumerate(context.findings, 1)
                    if f in selected_findings
                ]
                correction_context = context.copy(deep=True)
                correction_context.findings = selected_findings
                corrected_script = self.llm_agent.generate_corrected_script(
                    correction_context, findings_for_correction
                )
                if corrected_script:
                    report_lines.append("Corrected Script:")
                    report_lines.append("-" * 17)
                    report_lines.append("```bash")
                    report_lines.append(corrected_script)
                    report_lines.append("```")
                    report_lines.append("")

        return report_lines

    def _get_educational_description(self, category: str) -> str:
        """Get a short educational description for a finding category."""
        descriptions = {
            "LUSTRE": "Lustre is a high-performance file system used in HPC environments. Properly configuring it for your job can significantly improve I/O performance, especially for large files.",
            "RESOURCE": "Efficiently requesting and using resources like CPU, memory, and time is crucial in a shared HPC environment. This ensures your job runs smoothly and doesn't waste valuable resources.",
            "SHELL": "Your job script is a shell script. Following best practices for shell scripting can make your script more robust, reliable, and easier to debug.",
            "PERFORMANCE": "There are several ways to optimize your script for better performance. These recommendations focus on making your job run faster and more efficiently.",
            "SECURITY": "These recommendations are related to the security of your job and data. Following them can help prevent unauthorized access and protect your work.",
            "OTHER": "Here are some general recommendations for improving your job script.",
        }
        return descriptions.get(category, "")

    def _extract_tools(self, context: JobContext) -> str:
        """Extract tools mentioned in the script for the summary."""
        tools = set()
        for element in context.parsed_elements:
            if element.element_type == "TOOL_COMMAND" and element.value is not None: # Add None check here
                command = element.value.strip()
                if command:
                    tool = command.split()[0]
                    tools.add(tool)

        return ", ".join(sorted(tools)) if tools else "None detected"

