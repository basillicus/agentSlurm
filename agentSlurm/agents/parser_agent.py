import re
from typing import List
from agentSlurm.agents.base_agent import BaseAgent
from agentSlurm.models.job_context import JobContext, ParsedElement, UserCommand


class ParserAgent(BaseAgent):
    """
    The Parser Agent is responsible for converting raw script content
    into structured elements and extracting user commands from special comments.
    """
    
    def __init__(self):
        super().__init__(agent_id="Parser Agent")
        # Pattern to match SBATCH directives
        self.sbatch_pattern = re.compile(r'^\s*#SBATCH\s+([-\w]+)(?:\s+(.+?))?(?:\s*#.*)?$')
        # Pattern to match Agent SLURM comments
        self.agent_comment_pattern = re.compile(r'^\s*#\s*Agent SLURM:\s*(.+)$', re.IGNORECASE)
        # Pattern to match general commands
        self.command_pattern = re.compile(r'^\s*([^#\n].*)$')
    
    def run(self, context: JobContext) -> JobContext:
        """
        Parse the raw script into structured elements.
        
        Args:
            context: The JobContext containing the raw script
            
        Returns:
            The updated JobContext with parsed elements
        """
        self.log_trace(context, "Starting parsing", {"script_length": len(context.raw_script)})
        
        lines = context.raw_script.split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            # Check for SBATCH directives first
            sbatch_match = self.sbatch_pattern.match(line)
            if sbatch_match:
                key = sbatch_match.group(1)
                value = sbatch_match.group(2)
                element = ParsedElement(
                    element_type="SBATCH",
                    key=key,
                    value=value,
                    line_number=line_num,
                    raw_line=line
                )
                context.parsed_elements.append(element)
                continue
            
            # Check for Agent SLURM comments
            agent_match = self.agent_comment_pattern.match(line)
            if agent_match:
                message = agent_match.group(1).strip()
                command = UserCommand(
                    message=message,
                    line_number=line_num
                )
                context.user_commands.append(command)
                continue
            
            # Check for general commands (non-comment, non-empty lines)
            cmd_match = self.command_pattern.match(line)
            if cmd_match and cmd_match.group(1).strip():
                command_text = cmd_match.group(1).strip()
                # Identify if this is a Lustre command
                if command_text.startswith('lfs'):
                    element_type = "LUSTRE_COMMAND"
                elif any(tool in command_text for tool in ['bwa', 'gatk', 'samtools', 'fastqc', 'blastn', 'vasp']):
                    element_type = "TOOL_COMMAND"
                else:
                    element_type = "COMMAND"
                
                element = ParsedElement(
                    element_type=element_type,
                    value=command_text,
                    line_number=line_num,
                    raw_line=line
                )
                context.parsed_elements.append(element)
        
        self.log_trace(context, "Parsing completed", {
            "total_lines": len(lines),
            "parsed_elements": len(context.parsed_elements),
            "user_commands": len(context.user_commands)
        })
        
        return context