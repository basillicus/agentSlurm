"""
Knowledge Base Updater: Module to handle learning from LLM insights
and update the centralized knowledge base with new deterministic rules.
"""

import yaml

# import json
from typing import Dict, List, Any, Optional  # Added Optional
from pathlib import Path
import re
from datetime import datetime


class KnowledgeBaseUpdater:
    """
    Handles the process of converting LLM insights into deterministic rules
    and updating the knowledge base accordingly.
    """

    def __init__(self, kb_path: Optional[str] = None):
        _kb_path_str: str
        if kb_path is None:
            # Default to user's home directory to ensure write permissions
            _kb_path_str = str(
                Path.home() / ".agentslurm" / "knowledge_base" / "rules.yaml"
            )
        else:
            _kb_path_str = kb_path
        self.kb_path: Path = Path(_kb_path_str)  # Defined once here

        # Ensure directory exists
        if not self.kb_path.parent.exists():
            try:
                self.kb_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Warning: Could not create knowledge base directory: {e}")

        self.learned_rules: List[Dict[str, Any]] = []

    def add_learned_rules(self, rules: List[Dict[str, Any]]):
        """Add learned rules to be considered for knowledge base integration."""
        self.learned_rules.extend(rules)

    def validate_rule(self, rule: Dict[str, Any]) -> bool:
        """
        Validate that a learned rule has the necessary structure to be
        integrated into the knowledge base.
        """
        required_fields = ["rule_id", "description", "agent", "severity", "feedback"]

        for field in required_fields:
            if field not in rule:
                print(
                    f"Rule validation failed: Missing required field '{field}' in rule {rule.get('rule_id', 'unknown')}"
                )
                return False

        # Validate severity
        valid_severities = ["INFO", "WARNING", "ERROR"]
        if rule["severity"] not in valid_severities:
            print(
                f"Rule validation failed: Invalid severity '{rule['severity']}' in rule {rule.get('rule_id', 'unknown')}"
            )
            return False

        # Validate feedback structure
        feedback = rule["feedback"]
        required_profiles = ["Basic", "Medium", "Advanced"]
        for profile in required_profiles:
            if profile not in feedback:
                print(
                    f"Rule validation failed: Missing feedback for profile '{profile}' in rule {rule.get('rule_id', 'unknown')}"
                )
                return False
            if (
                not isinstance(feedback[profile], dict)
                or "title" not in feedback[profile]
                or "message" not in feedback[profile]
            ):
                print(
                    f"Rule validation failed: Invalid feedback structure for profile '{profile}' in rule {rule.get('rule_id', 'unknown')}"
                )
                return False

        return True

    def create_rule_from_pattern(self, pattern: str, context: str) -> Dict[str, Any]:
        """
        Create a rule definition based on a detected pattern in the script context.
        This is a simplified method - in a full implementation, this would be more sophisticated.
        """
        import hashlib

        # Generate a unique rule ID based on the pattern
        pattern_hash = hashlib.md5(pattern.encode()).hexdigest()[:8]
        rule_id = f"LEARNED-{pattern_hash.upper()}"

        # Create a basic rule structure
        rule = {
            "rule_id": rule_id,
            "description": f"Learned rule for pattern: {pattern[:50]}...",
            "agent": "Knowledge Base Updater",
            "severity": "WARNING",  # Default to warning for learned patterns
            "trigger_conditions": [
                {"type": "pattern_match", "pattern": pattern, "context": context}
            ],
            "feedback": {
                "Basic": {
                    "title": f"Potential issue detected: {pattern[:30]}...",
                    "message": f"The script contains a pattern that might cause issues: '{pattern}'. Consider reviewing this section.",
                },
                "Medium": {
                    "title": f"Pattern '{pattern}' detected",
                    "message": f"This script contains the pattern '{pattern}' which was identified by LLM analysis as potentially problematic. The recommended approach is to {self._suggest_fix_for_pattern(pattern)}.",
                },
                "Advanced": {
                    "title": f"Suboptimal pattern: {pattern}",
                    "message": f"The pattern '{pattern}' may lead to performance or configuration issues. Consider implementing {self._suggest_fix_for_pattern(pattern)} for optimal results.",
                },
            },
            "documentation_url": None,
            "learned_from_llm": True,
            "confidence": 0.8,  # Default confidence for learned rules
            "created_at": datetime.now().isoformat(),
        }

        return rule

    def _suggest_fix_for_pattern(self, pattern: str) -> str:
        """
        Suggest a fix based on the pattern detected.
        This is a simple implementation - in a real system, this would be more intelligent.
        """
        pattern_lower = pattern.lower()

        if "lfs setstripe" in pattern_lower and "-c 1" not in pattern_lower:
            return "using appropriate Lustre striping (consider lfs setstripe -c 1 for small files or appropriate values for large files)"
        elif "set -e" not in pattern_lower:
            return "adding 'set -e' to ensure script exits on error"
        elif "module load" in pattern_lower:
            return "ensuring all required modules are loaded before use"
        elif "SBATCH" in pattern_lower:
            return "reviewing SBATCH directives for optimal resource allocation"
        else:
            return "reviewing this pattern against HPC best practices"

    def analyze_and_create_rules(
        self, script_content: str, llm_insights: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Analyze script content and LLM insights to create new rules.
        """
        new_rules = []

        # Extract patterns from LLM insights that could become rules
        for insight in llm_insights:
            if (
                "message" in insight and len(insight["message"]) > 10
            ):  # Meaningful insight
                # Look for specific patterns in the insight message
                patterns = self._extract_patterns_from_insight(insight, script_content)

                for pattern in patterns:
                    rule = self.create_rule_from_pattern(pattern, script_content[:200])
                    if self.validate_rule(rule):
                        new_rules.append(rule)

        return new_rules

    def _extract_patterns_from_insight(
        self, insight: Dict[str, Any], script_content: str
    ) -> List[str]:
        """
        Extract specific patterns from an LLM insight that could become rules.
        """
        patterns = []
        message = insight.get("message", "")

        # Look for code snippets or commands mentioned in the insight
        code_patterns = re.findall(r"`([^`]+)`", message)  # Code in backticks
        command_patterns = re.findall(
            r"([a-zA-Z][a-zA-Z0-9_-]+\s+[^\s]+)", message
        )  # Commands with args

        # Combine and filter patterns
        all_patterns = code_patterns + command_patterns

        for pattern in all_patterns:
            pattern = pattern.strip()
            if len(pattern) > 5 and len(pattern) < 100:  # Reasonable length
                patterns.append(pattern)

        # If no specific patterns found, use key phrases from the message
        if not patterns:
            # Extract key phrases related to HPC/SLURM concepts
            hpc_keywords = [
                "SBATCH",
                "lfs",
                "setstripe",
                "module",
                "srun",
                "mpirun",
                "export",
                "ulimit",
            ]
            for keyword in hpc_keywords:
                if keyword.lower() in message.lower():
                    # Find context around the keyword
                    start = max(0, message.lower().find(keyword.lower()) - 20)
                    end = min(len(message), message.lower().find(keyword.lower()) + 40)
                    context = message[start:end].strip()
                    if context and context not in patterns:
                        patterns.append(context)

        return list(set(patterns))  # Remove duplicates

    def update_knowledge_base(
        self, new_rules: List[Dict[str, Any]], backup: bool = True
    ) -> bool:
        """
        Update the knowledge base with new rules.
        """
        try:
            # Backup existing knowledge base if requested
            if backup and self.kb_path.exists():
                backup_path = self.kb_path.with_suffix(
                    f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
                )
                import shutil

                shutil.copy2(self.kb_path, backup_path)
                print(f"Backed up knowledge base to: {backup_path}")

            # Load existing knowledge base
            if self.kb_path.exists():
                with open(self.kb_path, "r") as f:
                    kb_data = yaml.safe_load(f) or {}
            else:
                # Create new knowledge base structure
                kb_data = {
                    "version": "1.0.0",
                    "last_updated": datetime.now().isoformat(),
                    "slurm_rules": [],
                    "lustre_rules": [],
                    "workflow_patterns": [],
                    "general_logic_rules": [],
                }

            # Add new rules to the knowledge base
            # For now, add them to general_logic_rules, but this could be more sophisticated
            for rule in new_rules:
                # Determine the appropriate section based on rule characteristics
                if (
                    "lfs" in rule["description"].lower()
                    or "lustre" in rule["description"].lower()
                ):
                    kb_data["lustre_rules"].append(rule)
                elif any(
                    sbatch in rule["description"].lower()
                    for sbatch in ["sbatch", "resource", "memory", "cpu", "time"]
                ):
                    kb_data["slurm_rules"].append(rule)
                else:
                    kb_data["general_logic_rules"].append(rule)

            # Update timestamp
            kb_data["last_updated"] = datetime.now().isoformat()
            kb_data["version"] = "1.0.1"  # Increment version

            # Write updated knowledge base
            with open(self.kb_path, "w") as f:
                yaml.dump(kb_data, f, default_flow_style=False, indent=2)

            print(
                f"Successfully updated knowledge base with {len(new_rules)} new rules"
            )
            print(f"Total rules in knowledge base: {self._count_total_rules(kb_data)}")

            return True

        except Exception as e:
            print(f"Error updating knowledge base: {e}")
            return False

    def _count_total_rules(self, kb_data: Dict) -> int:
        """Count total rules in knowledge base."""
        total = 0
        for key in kb_data:
            if isinstance(kb_data[key], list):
                total += len(kb_data[key])
        return total

    def run_learning_pipeline(
        self, script_content: str, llm_insights: List[Dict], auto_update: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Complete learning pipeline: analyze insights, create rules, optionally update KB.
        """
        print("Running knowledge base learning pipeline...")

        # Analyze and create new rules
        new_rules = self.analyze_and_create_rules(script_content, llm_insights)

        if not new_rules:
            print("No new rules generated from LLM insights")
            return []

        print(f"Generated {len(new_rules)} potential new rules from LLM insights")

        # Validate rules
        validated_rules = []
        for rule in new_rules:
            if self.validate_rule(rule):
                validated_rules.append(rule)
            else:
                print(f"Skipping invalid rule: {rule.get('rule_id', 'unknown')}")

        print(f"Validated {len(validated_rules)} rules for knowledge base integration")

        # Update knowledge base if requested
        if auto_update and validated_rules:
            success = self.update_knowledge_base(validated_rules)
            if success:
                print("Knowledge base successfully updated with new rules")
            else:
                print("Failed to update knowledge base")

        return validated_rules


def integrate_learned_rules_from_llm_agent(
    llm_agent, script_content: str, kb_path: Optional[str] = None
):
    """
    Convenience function to integrate rules learned by the LLM agent into the knowledge base.
    """
    updater = KnowledgeBaseUpdater(kb_path)

    # Get learned rules from LLM agent
    learned_rules = llm_agent.get_learned_rules()

    if not learned_rules:
        print("No learned rules to integrate from LLM agent")
        return []

    # Run the learning pipeline to integrate them
    integrated_rules = updater.run_learning_pipeline(
        script_content=script_content, llm_insights=learned_rules, auto_update=True
    )

    return integrated_rules

