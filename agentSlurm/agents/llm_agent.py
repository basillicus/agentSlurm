from __future__ import annotations # Added for forward references
from typing import Dict, List, Optional, Any
from agentSlurm.agents.base_agent import BaseAgent
from agentSlurm.models.job_context import JobContext, Finding, Severity, UserProfile
import json
from datetime import datetime
import re


class LLMAgent(BaseAgent):
    """
    The LLM Agent leverages large language models to perform deeper analysis
    of SLURM scripts when rule-based analysis is insufficient. It also learns
    from novel patterns to create new deterministic rules for the knowledge base.
    """

    def __init__(
        self, llm_provider="openai", model="gpt-3.5-turbo", api_key=None, base_url=None
    ):
        super().__init__(agent_id="LLM Agent")
        self.llm_provider = llm_provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.llm_client = self._initialize_llm_client()

        # Knowledge base of patterns learned from LLM analysis
        self.learned_patterns = {}

    def _initialize_llm_client(self):
        """Initialize the appropriate LLM client based on provider."""
        if self.llm_provider == "openai":
            from openai import OpenAI

            client_params = {"api_key": self.api_key}
            if self.base_url:
                client_params["base_url"] = self.base_url
            return OpenAI(**client_params)
        elif self.llm_provider == "anthropic":
            from anthropic import Anthropic

            client_params = {"api_key": self.api_key}
            if self.base_url:
                client_params["base_url"] = self.base_url
            return Anthropic(**client_params)
        elif self.llm_provider == "ollama":
            from openai import OpenAI

            # Ollama is compatible with OpenAI's API format
            base_url = self.base_url or "http://localhost:11434/v1"
            return OpenAI(
                base_url=base_url, api_key="ollama"
            )  # Ollama doesn't require real API key
        elif self.llm_provider == "huggingface":
            from huggingface_hub import InferenceClient

            # For Hugging Face, we use the InferenceClient
            client_params = {"token": self.api_key} if self.api_key else {}
            if self.base_url:
                # Use custom endpoint if provided
                return InferenceClient(model=self.base_url, **client_params)
            else:
                return InferenceClient(model=self.model, **client_params)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    def run(self, context: JobContext) -> JobContext:
        """
        Use LLM to analyze sections of the script that weren't caught by
        rule-based analysis, and identify new patterns for knowledge base.

        Args:
            context: The JobContext containing all previous analysis results

        Returns:
            The updated JobContext with LLM findings and learned patterns
        """
        self.log_trace(context, "Starting LLM analysis")

        # Identify sections that need LLM analysis
        analysis_needed = self._identify_analysis_needed(context)

        if analysis_needed:
            # Perform LLM-based analysis
            llm_findings = self._analyze_with_llm(context, analysis_needed)
            context.findings.extend(llm_findings)

            # Learn from LLM insights and create new rules
            self._learn_from_llm_insights(context, llm_findings)

        self.log_trace(
            context,
            "LLM analysis completed",
            {
                "findings_added": len(
                    [f for f in context.findings if f.agent_id == self.agent_id]
                )
            },
        )

        return context

    def _identify_analysis_needed(self, context: JobContext) -> List[Dict]:
        """
        Identify parts of the script that might need deeper analysis.
        These are typically sections that the rule-based agents didn't analyze
        or where there are complex interactions not covered by current rules.
        """
        sections_to_analyze = []

        # Check for complex shell logic that might not be parsed correctly by rules
        complex_logic_indicators = [
            "if ",
            "then",
            "else",
            "fi",
            "for ",
            "while ",
            "do",
            "done",
            "case",
            "esac",
            "function",
            "&&",
            "||",
            "{",
            "}",
        ]

        # Get lines not covered by existing findings
        covered_lines = {f.line_number for f in context.findings if f.line_number}

        for element in context.parsed_elements:
            if element.line_number not in covered_lines:
                # Check if this contains complex logic
                if any(
                    indicator in element.raw_line.lower()
                    for indicator in complex_logic_indicators
                ):
                    sections_to_analyze.append(
                        {
                            "element": element,
                            "context": self._get_context_around_line(
                                context, element.line_number
                            ),
                        }
                    )

        # Also include the full script if no significant issues were found by rule-based agents
        # This allows the LLM to do a comprehensive review
        if len(context.findings) < 2:  # If very few findings, do comprehensive check
            sections_to_analyze.append(
                {
                    "element": None,
                    "context": {
                        "full_script": context.raw_script,
                        "parsed_elements": [e.dict() for e in context.parsed_elements],
                        "user_profile": context.user_profile.value,
                    },
                }
            )

        return sections_to_analyze

    def _get_context_around_line(
        self, context: JobContext, line_number: int, window: int = 3
    ) -> Dict:
        """Get context around a specific line to provide to the LLM."""
        lines = context.raw_script.split("\n")
        start = max(0, line_number - window - 1)
        end = min(len(lines), line_number + window)

        return {
            "around_line": lines[start:end],
            "target_line_number": line_number,
            "parsed_elements_nearby": [
                e.dict()
                for e in context.parsed_elements
                if start <= e.line_number - 1 <= end
            ],
            "user_profile": context.user_profile.value,
        }

    def _analyze_with_llm(
        self, context: JobContext, sections_to_analyze: List[Dict]
    ) -> List[Finding]:
        """Use LLM to analyze specific sections of the script."""
        findings = []

        for section in sections_to_analyze:
            try:
                if section["element"] is None:  # Full script analysis
                    analysis_prompt = self._create_comprehensive_analysis_prompt(
                        section["context"]["full_script"], context.user_profile
                    )
                else:  # Specific section analysis
                    analysis_prompt = self._create_section_analysis_prompt(
                        section, context.user_profile
                    )

                llm_response = self._call_llm(analysis_prompt)

                # Parse LLM response into findings
                parsed_findings = self._parse_llm_response(
                    context, llm_response, context.user_profile
                )
                findings.extend(parsed_findings)

            except Exception as e:
                self.log_trace(
                    context,
                    "LLM analysis failed",
                    {"error": str(e), "section": str(section)[:100] + "..."},
                )

        return findings

    def _create_comprehensive_analysis_prompt(
        self, script: str, user_profile: UserProfile
    ) -> str:
        """Create prompt for comprehensive script analysis."""
        profile_desc = {
            UserProfile.BASIC: "a beginner HPC user",
            UserProfile.MEDIUM: "an intermediate HPC user",
            UserProfile.ADVANCED: "an advanced HPC user",
        }[user_profile]

        return f"""
        You are an expert HPC and SLURM script analyzer. Analyze this SLURM script for potential issues, optimizations, and best practices. 
        The user is {profile_desc}.

        SLURM Script:
        {script}

        Analyze for:
        1. Resource allocation issues (memory, CPU, time, nodes)
        2. Lustre filesystem optimization opportunities
        3. Shell scripting best practices (error handling, variable usage)
        4. Potential performance bottlenecks
        5. Security considerations
        6. Any other issues you identify

        Respond in JSON format with the following structure:
        {{
            "findings": [
                {{
                    "rule_id": "LLM-XXXX" (generate a unique ID),
                    "severity": "INFO|WARNING|ERROR",
                    "title": "Short title of the issue",
                    "message": "Detailed explanation appropriate for the user level",
                    "line_number": null or specific line number,
                    "category": "RESOURCE|LUSTRE|SHELL|PERFORMANCE|SECURITY|OTHER"
                }}
            ]
        }}

        Keep explanations appropriate for the user's experience level. For BASIC, focus on practical implications. For MEDIUM, include technical details. For ADVANCED, include specific technical recommendations.
        """

    def _create_section_analysis_prompt(
        self, section: Dict, user_profile: UserProfile
    ) -> str:
        """Create prompt for specific section analysis."""
        profile_desc = {
            UserProfile.BASIC: "a beginner HPC user",
            UserProfile.MEDIUM: "an intermediate HPC user",
            UserProfile.ADVANCED: "an advanced HPC user",
        }[user_profile]

        context_info = section["context"]

        return f"""
        You are an expert HPC and SLURM script analyzer. Analyze this section of a SLURM script for potential issues and optimizations.
        The user is {profile_desc}.

        Context around the line:
        {chr(10).join(context_info["around_line"])}

        The specific line is around line number {context_info["target_line_number"]}.

        Analyze for:
        1. Logic errors or potential issues
        2. Performance considerations
        3. Best practices
        4. Potential optimizations
        5. Any other issues you identify

        Respond in JSON format with the following structure:
        {{
            "findings": [
                {{
                    "rule_id": "LLM-XXXX" (generate a unique ID),
                    "severity": "INFO|WARNING|ERROR",
                    "title": "Short title of the issue",
                    "message": "Detailed explanation appropriate for the user level",
                    "line_number": {context_info["target_line_number"]},
                    "category": "LOGIC|PERFORMANCE|BEST_PRACTICE|OTHER"
                }}
            ]
        }}

        Keep explanations appropriate for the user's experience level.
        """

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the given prompt."""
        if self.llm_provider in ["openai", "ollama"]:
            try:
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=4096,
                )
                content = response.choices[0].message.content
                print(f"[DEBUG] LLM Response received, length: {len(content)}")
                return content
            except Exception as e:
                print(f"[DEBUG] Error calling {self.llm_provider}: {e}")
                # Return a structured response for debugging
                return f'{{"findings": [{{"rule_id": "{self.llm_provider.upper()}-ERROR", "severity": "INFO", "title": "API Error", "message": "{str(e)}"}}]}}'
        elif self.llm_provider == "anthropic":
            try:
                response = self.llm_client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = (
                    response.content[0].text
                    if hasattr(response.content[0], "text")
                    else str(response.content[0])
                )
                print(f"[DEBUG] Anthropic Response received, length: {len(content)}")
                return content
            except Exception as e:
                print(f"[DEBUG] Error calling Anthropic: {e}")
                return f'{{"findings": [{{"rule_id": "ANTHROPIC-ERROR", "severity": "INFO", "title": "API Error", "message": "{str(e)}"}}]}}'
        elif self.llm_provider == "huggingface":
            try:
                # Use the 'chat_completion' for conversational tasks
                response = self.llm_client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4096,
                    temperature=0.2,
                )
                if hasattr(response, "choices") and response.choices:
                    return response.choices[0].message.content
                else:
                    return str(response)
            except Exception as e:
                print(f"[DEBUG] Hugging Face API error: {e}")
                # Return a structured response in case of error
                return f'{{ "findings": [{{ "rule_id": "HF-ERROR", "severity": "INFO", "title": "API Error", "message": "Hugging Face API error: {str(e)}" }}] }}'
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    def _parse_llm_response(
        self, context: JobContext, response: str, user_profile: UserProfile
    ) -> List[Finding]:
        """Parse the LLM response into Finding objects."""
        try:
            # Extract JSON from the response if it's wrapped in markdown code block
            original_response = response
            if "```json" in response:
                start = response.find("```json") + len("```json")
                end = response.find("```", start)
                if end == -1:  # If no closing ``` found, take to end of string
                    end = len(response)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```")
                if start != -1:
                    # Find the start of the content after the first ```
                    next_newline = response.find("\n", start)
                    if next_newline != -1:
                        start = next_newline + 1
                    else:
                        start = start + 3
                    end = response.find("```", start)
                    if end == -1:  # If no closing ``` found, take to end of string
                        end = len(response)
                    json_str = response[start:end].strip()
                else:
                    json_str = response.strip()
            else:
                json_str = response.strip()

            # Clean up the JSON string further
            json_str = json_str.strip()
            if json_str.startswith("{") or json_str.startswith("["):
                data = json.loads(json_str)
            else:
                # Try to extract JSON from within the string
                # Look for JSON object patterns
                import re

                json_match = re.search(r"(\{.*\}|\[.*\])", response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    raise json.JSONDecodeError("No valid JSON found", response, 0)

            findings = []

            for finding_data in data.get("findings", []):
                # Validate required fields exist
                rule_id = finding_data.get("rule_id", "LLM-UNKNOWN")
                severity_str = finding_data.get("severity", "INFO").upper()

                # Validate severity - check if the string value is valid
                valid_severities = {
                    "INFO": Severity.INFO,
                    "WARNING": Severity.WARNING,
                    "ERROR": Severity.ERROR,
                }
                if severity_str in valid_severities:
                    severity = valid_severities[severity_str]
                else:
                    # Also check lowercase versions
                    severity_lower = severity_str.lower()
                    if severity_lower.upper() in valid_severities:
                        severity = valid_severities[severity_lower.upper()]
                    else:
                        print(
                            f"[DEBUG] Invalid severity value: '{severity_str}', defaulting to INFO"
                        )
                        severity = Severity.INFO  # Default to INFO if invalid severity

                finding = Finding(
                    agent_id=self.agent_id,
                    rule_id=rule_id,
                    severity=severity,
                    title=finding_data.get("title", "Unknown issue"),
                    message=finding_data.get("message", "No description provided"),
                    line_number=finding_data.get("line_number"),
                    category=finding_data.get("category", "OTHER"),
                    confidence=0.8,  # LLM findings have medium confidence initially
                )
                findings.append(finding)

            return findings

        except json.JSONDecodeError as e:
            # Log the error for debugging
            self._log_debug_info(context, original_response, str(e))

            # If JSON parsing fails, create findings based on the raw response
            # Split the response into more manageable chunks to avoid truncation
            response_chunks = self._split_response_into_chunks(
                original_response, max_chunk_size=4000
            )
            findings = []

            for i, chunk in enumerate(response_chunks):
                findings.append(
                    Finding(
                        agent_id=self.agent_id,
                        rule_id=f"LLM-UNPARSED-{i + 1}",
                        severity=Severity.INFO,
                        title="LLM Analysis Result (Unparsed)",
                        message=f"LLM response (part {i + 1}): {chunk[:3000]}...[truncated]",
                        confidence=0.3,  # Low confidence for unparsed responses
                    )
                )

            return findings
        except Exception as e:
            # Log any other errors
            self._log_debug_info(context, original_response, f"Unexpected error: {str(e)}")
            return [
                Finding(
                    agent_id=self.agent_id,
                    rule_id="LLM-ERROR",
                    severity=Severity.INFO,
                    title="LLM Processing Error",
                    message=f"Error processing LLM response: {str(e)}. Raw response: {original_response[:500]}...",
                    confidence=0.1,
                )
            ]

    def _log_debug_info(self, context: JobContext, response: str, error: Optional[str] = None):
        """Log debugging information for LLM response parsing issues."""
        debug_info = {
            "timestamp": datetime.now().isoformat(),
            "original_response_length": len(response),
            "original_response_preview": response[:1000],
            "error": error,
            "response_lines_count": len(response.split("\n")),
            "has_json_markers": "```json" in response or "```" in response,
            "has_curly_braces": "{" in response and "}" in response,
        }

        # Log to trace
        self.log_trace(context, "LLM Response Debug Info", debug_info)

        # Print to console for immediate debugging
        print(f"[DEBUG] LLM Response Analysis:")
        print(f"[DEBUG] Response length: {len(response)}")
        print(f"[DEBUG] Has JSON markers: {debug_info['has_json_markers']}")
        print(f"[DEBUG] Has curly braces: {debug_info['has_curly_braces']}")
        print(f"[DEBUG] Error: {error}")
        print(f"[DEBUG] First 200 chars: {response[:200]}")
        if error:
            print(f"[DEBUG] Error context: {error}")

    def _split_response_into_chunks(
        self, response: str, max_chunk_size: int = 4000
    ) -> List[str]:
        """Split a long response into chunks that fit within the max size."""
        if len(response) <= max_chunk_size:
            return [response]

        chunks = []
        for i in range(0, len(response), max_chunk_size):
            chunks.append(response[i: i + max_chunk_size])
        return chunks

    def _learn_from_llm_insights(self, context: JobContext, findings: List[Finding]):
        """
        Extract patterns from LLM findings to create new deterministic rules
        for the knowledge base.
        """
        for finding in findings:
            # Only learn from findings that seem to represent recurring patterns
            if finding.confidence >= 0.7:  # High confidence LLM findings
                self._extract_pattern_for_rule_creation(finding, context)

    def _extract_pattern_for_rule_creation(self, finding: Finding, context: JobContext):
        """
        Extract a pattern from an LLM finding that could become a deterministic rule.
        """
        # Create a potential rule from the finding if it seems like a common pattern
        pattern_key = f"{finding.rule_id}_{finding.title}"

        if pattern_key not in self.learned_patterns:
            rule_suggestion = {
                "rule_id": finding.rule_id,
                "description": finding.title,
                "agent": "LLM Learned Rule",
                "severity": finding.severity.value,
                "trigger_conditions": self._infer_conditions_from_context(
                    finding, context
                ),
                "feedback": {
                    "Basic": {"title": finding.title, "message": finding.message},
                    "Medium": {"title": finding.title, "message": finding.message},
                    "Advanced": {"title": finding.title, "message": finding.message},
                },
                "created_from_llm_finding": True,
                "created_at": datetime.now().isoformat(),
                "script_sample": context.raw_script[
                    :500
                ],  # Store example script context
            }

            self.learned_patterns[pattern_key] = rule_suggestion
            self.log_trace(
                context,
                "Learned new pattern from LLM",
                {"rule_id": finding.rule_id, "description": finding.title},
            )

    def _infer_conditions_from_context(
        self, finding: Finding, context: JobContext
    ) -> List[Dict]:
        """
        Attempt to infer conditions that would trigger this rule based on context.
        This is a simplified approach - in a real implementation, this would be more sophisticated.
        """
        conditions = []

        # Look for common patterns in the script that might have triggered this finding
        if (
            "lfs" in context.raw_script.lower()
            or "lustre" in context.raw_script.lower()
        ):
            conditions.append({"type": "filesystem_usage", "pattern": "lustre_related"})

        if any(
            tool in context.raw_script.lower()
            for tool in ["bwa", "gatk", "samtools", "vasp"]
        ):
            conditions.append({"type": "tool_usage", "pattern": "large_file_tools"})

        if any(
            tool in context.raw_script.lower()
            for tool in ["fastqc", "multiqc", "blast"]
        ):
            conditions.append({"type": "tool_usage", "pattern": "small_file_tools"})

        # Add generic condition based on finding category (inferred from title/message)
        if "memory" in finding.title.lower() or "memory" in finding.message.lower():
            conditions.append({"type": "resource_check", "pattern": "memory_related"})

        if not conditions:
            conditions.append({"type": "general", "pattern": "script_analysis"})

        return conditions

    def get_learned_rules(self) -> List[Dict]:
        """Return the rules learned from LLM insights that could be added to knowledge base."""
        return list(self.learned_patterns.values())

    def generate_corrected_script(self, context: JobContext, findings_for_correction: List[tuple[int, Any]]) -> Optional[str]:
        """
        Generate a corrected version of the script based on the findings.

        Args:
            context: The JobContext containing the original script and findings.
            findings_for_correction: A list of tuples, where each tuple contains the original finding number and the finding object.

        Returns:
            The corrected script as a string, or None if no corrections are needed.
        """
        if not findings_for_correction:
            return None

        self.log_trace(context, "Generating corrected script")

        # Create a summary of the findings to provide to the LLM
        findings_summary = []
        for i, finding in findings_for_correction:
            line_ref = f" (line {finding.line_number})" if finding.line_number else ""
            findings_summary.append(f"{i}. {finding.title}{line_ref}: {finding.message}")
        
        correction_prompt = self._create_correction_prompt(
            context.raw_script,
            "\n".join(findings_summary),
            context.user_profile
        )
        
        try:
            corrected_script = self._call_llm(correction_prompt)
            # Extract the script from the response, assuming it's in a code block
            if "```" in corrected_script:
                start = corrected_script.find("```") + 3
                # Find the start of the content after the first ```
                next_newline = corrected_script.find('\n', start)
                if next_newline != -1:
                    start = next_newline + 1
                else:
                    start = start + 3
                end = corrected_script.find("```", start)
                if end != -1:
                    return corrected_script[start:end].strip()
            return corrected_script.strip()
        except Exception as e:
            self.log_trace(context, "Corrected script generation failed", {"error": str(e)})
            return f"# Error generating corrected script: {e}"

    def _create_correction_prompt(
        self, script: str, findings_summary: str, user_profile: UserProfile
    ) -> str:
        """Create a prompt for generating a corrected script."""
        profile_instructions = {
            UserProfile.BASIC: "Prioritize correctness and clarity above all else. Only correct critical errors that would prevent the script from running. Do not add complex logic or advanced features that are not essential for the script's main purpose. Strive for the simplest possible script that is correct and easy to understand.",
            UserProfile.MEDIUM: "Correct all identified issues and apply common optimizations. The script should be robust and efficient, but still easy to read and maintain.",
            UserProfile.ADVANCED: "Apply all best practices and advanced optimizations, even if they increase complexity. The script should be as performant and robust as possible.",
        }[user_profile]

        return f"""
        You are an expert HPC and SLURM script analyzer. Based on the following analysis, please provide a corrected version of the SLURM script.

        The user is a {user_profile.value} HPC user.

        Original SLURM Script:
        ```bash
        {script}
        ```

        Analysis Findings:
        {findings_summary}

        Instructions:
        1.  Correct the script based on the findings.
        2.  {profile_instructions}
        3.  Add comments to the script explaining the changes. The comments should reference the finding number (e.g., "# Finding 1: ...").
        4.  The corrected script should be a single block of code, ready to be saved and executed.
        5.  Enclose the corrected script in a single markdown code block (```bash ... ```).
        """

    def export_learned_rules_for_kb(self, filename: Optional[str] = None) -> str:
        """
        Export learned rules in a format suitable for adding to the knowledge base.
        """
        import yaml
        from datetime import datetime

        rules_for_kb = {
            "version": "1.0.0",
            "exported_at": datetime.now().isoformat(),
            "learned_rules": list(self.learned_patterns.values()),
            "description": "Rules generated by LLM analysis that could be converted to deterministic rules",
        }

        yaml_content = yaml.dump(rules_for_kb, default_flow_style=False, indent=2)

        if filename:
            with open(filename, "w") as f:
                f.write(yaml_content)

        return yaml_content
