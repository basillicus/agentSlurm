from agentSlurm.agents.base_agent import BaseAgent
from agentSlurm.models.job_context import JobContext
from agentSlurm.utils.knowledge_base_updater import KnowledgeBaseUpdater
from typing import List, Dict, Any


class LearningAgent(BaseAgent):
    """
    The Learning Agent processes insights from LLM analysis and converts them 
    into deterministic rules for the knowledge base. This agent represents the
    core learning capability of the system.
    """

    def __init__(self):
        super().__init__(agent_id="Learning Agent")
        self.kb_updater = KnowledgeBaseUpdater()

    def run(self, context: JobContext) -> JobContext:
        """
        Process LLM insights and convert them to deterministic rules in the knowledge base.

        Args:
            context: The JobContext containing all analysis results including LLM findings

        Returns:
            The updated JobContext
        """
        self.log_trace(context, "Starting learning process from analysis results")
        
        # Extract LLM-based findings that could become deterministic rules
        llm_findings = [f for f in context.findings if f.agent_id == "LLM Agent"]
        
        if llm_findings:
            print(f"[LEARNING AGENT] Found {len(llm_findings)} LLM-generated insights to evaluate for rule creation")
            
            # Convert LLM findings to potential rules
            potential_rules = self._convert_findings_to_rules(llm_findings, context)
            
            if potential_rules:
                print(f"[LEARNING AGENT] Generated {len(potential_rules)} potential rules from LLM insights")
                
                # Validate and integrate rules into knowledge base
                integrated_rules = self.kb_updater.run_learning_pipeline(
                    script_content=context.raw_script,
                    llm_insights=potential_rules,
                    auto_update=True
                )
                
                print(f"[LEARNING AGENT] Successfully integrated {len(integrated_rules)} new rules into knowledge base")
                
                # Add a summary finding to the context about the learning
                if integrated_rules:
                    from agentSlurm.models.job_context import Finding, Severity
                    learning_finding = Finding(
                        agent_id=self.agent_id,
                        rule_id="LEARNING-001",
                        severity=Severity.INFO,
                        title="Knowledge Base Updated",
                        message=f"The system learned {len(integrated_rules)} new patterns from this analysis, which will improve future detections.",
                        confidence=1.0
                    )
                    context.findings.append(learning_finding)
        else:
            print("[LEARNING AGENT] No LLM insights found to learn from")
        
        self.log_trace(context, "Learning process completed", {
            "llm_findings_processed": len(llm_findings),
            "rules_integrated": len([f for f in context.findings if f.agent_id == self.agent_id])
        })
        
        return context

    def _convert_findings_to_rules(self, findings: List, context: JobContext) -> List[Dict[str, Any]]:
        """
        Convert LLM findings into rule structures suitable for the knowledge base.
        """
        potential_rules = []
        
        for finding in findings:
            # Extract key information from the finding to create a rule
            rule = {
                "rule_id": f"DYNAMIC-{finding.rule_id.replace('LLM-', '')}",
                "description": finding.title,
                "agent": "Lustre Agent",  # Assume it's a Lustre-related rule for now, but could be more sophisticated
                "severity": finding.severity.value,
                "trigger_conditions": self._infer_conditions_from_finding(finding, context),
                "feedback": self._generate_feedback_for_rule(finding),
                "confidence_from_llm": finding.confidence,
                "learned_from_analysis": True,
                "created_from_finding": finding.rule_id
            }
            potential_rules.append(rule)
        
        return potential_rules

    def _infer_conditions_from_finding(self, finding: Any, context: JobContext) -> List[Dict[str, str]]:
        """
        Infer the conditions that would trigger this rule based on the finding and script context.
        """
        conditions = []
        
        # Analyze the script to infer likely trigger conditions
        script_lower = context.raw_script.lower()
        
        # Look for patterns in the script that match the finding's subject
        if "lfs setstripe" in finding.title.lower() or "lustre" in finding.title.lower():
            conditions.append({
                "type": "lustre_command_check",
                "pattern": "lfs setstripe" if "setstripe" in script_lower else "lustre filesystem usage"
            })
        
        # Check for specific tools that might be related
        common_tools = ["bwa", "gatk", "samtools", "fastqc", "blast", "vasp", "star", "hisat2"]
        for tool in common_tools:
            if tool in script_lower and tool in finding.message.lower():
                conditions.append({
                    "type": "tool_usage",
                    "tool": tool
                })
        
        # If no specific conditions found, use a general condition
        if not conditions:
            conditions.append({
                "type": "script_analysis",
                "description": f"Finding related to: {finding.title}"
            })
        
        return conditions

    def _generate_feedback_for_rule(self, finding: Any) -> Dict[str, Dict[str, str]]:
        """
        Generate feedback messages at different user levels from the LLM finding.
        """
        # Use the LLM finding directly as the base, but customize for different user levels
        title = finding.title
        message = finding.message
        
        return {
            "Basic": {
                "title": title,
                "message": f"Your script contains a pattern that may cause issues: {message}. Consider reviewing this section."
            },
            "Medium": {
                "title": title,
                "message": f"This script pattern may be suboptimal: {message}. The recommended approach is to follow HPC best practices for this situation."
            },
            "Advanced": {
                "title": title,
                "message": f"Suboptimal configuration detected: {message}. Consider implementing the recommended optimization for better performance."
            }
        }