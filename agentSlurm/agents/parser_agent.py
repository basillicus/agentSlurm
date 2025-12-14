import re
from typing import List, Any
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor
from parsimonious.exceptions import ParseError
from agentSlurm.agents.base_agent import BaseAgent
from agentSlurm.models.job_context import JobContext, ParsedElement, UserCommand


class SlurmScriptVisitor(NodeVisitor):
    """
    Visitor to traverse the parsed Slurm script and build structured elements.
    """
    def __init__(self):
        self.parsed_elements = []
        self.user_commands = []
        self.current_line_num = 0

    def visit_line(self, node, visited_children):
        """
        Process a line node. We increment the line number counter here.
        Note: parsimonious doesn't track line numbers automatically in the way we want,
        so we approximate or need to rely on the node position if we parsed the whole file.
        However, since 'script' is a sequence of lines, we can just count.
        """
        self.current_line_num += 1
        return visited_children

    def visit_sbatch(self, node, visited_children):
        """Handle #SBATCH directives."""
        # visited_children structure depends on the grammar rules
        # sbatch = ws "#SBATCH" ws (option_value / option_flag) (ws comment_text)?
        # Index 3 is the (option_value / option_flag) group
        
        # The choice node returns a list containing the result of the chosen alternative.
        # Sometimes parsimonious might collapse nodes or pass through simple strings 
        # depending on visitor behavior, so we handle both dict (from visit_option_value/flag)
        # and string (if it fell through to option_key).
        choice_result = visited_children[3]
        if isinstance(choice_result, list) and choice_result:
             directive_data = choice_result[0]
        else:
             directive_data = choice_result

        key = None
        value = None

        if isinstance(directive_data, dict):
            key = directive_data.get('key')
            value = directive_data.get('value')
        elif isinstance(directive_data, str):
            # If we got a raw string, it's likely just the key (flag)
            key = directive_data
            value = None
        
        if key:
            element = ParsedElement(
                element_type="SBATCH",
                key=key,
                value=value,
                line_number=self.current_line_num,
                raw_line=node.text.strip()
            )
            self.parsed_elements.append(element)

    def visit_option_value(self, node, visited_children):
        """Handle --key=value or --key value."""
        key = visited_children[0]
        value = visited_children[3]
        return {'key': key, 'value': value}

    def visit_option_flag(self, node, visited_children):
        """Handle --flag."""
        key = visited_children[0]
        return {'key': key, 'value': None}

    def visit_option_key(self, node, visited_children):
        return node.text

    def visit_option_val(self, node, visited_children):
        return node.text

    def visit_agent_comment(self, node, visited_children):
        """Handle # Agent SLURM: message."""
        message = visited_children[5] # Index 5 is the message part
        command = UserCommand(
            message=message.strip(),
            line_number=self.current_line_num
        )
        self.user_commands.append(command)

    def visit_message(self, node, visited_children):
        return node.text

    def visit_command(self, node, visited_children):
        """Handle general commands."""
        command_text = node.text.strip()
        
        # Strip trailing comments if captured (grammar handles this, but let's be safe)
        if '#' in command_text:
            command_text = command_text.split('#')[0].strip()

        if not command_text:
            return

        # Simple classification logic (preserved from original)
        if command_text.startswith('lfs'):
            element_type = "LUSTRE_COMMAND"
        elif any(tool in command_text for tool in ['bwa', 'gatk', 'samtools', 'fastqc', 'blastn', 'vasp']):
            element_type = "TOOL_COMMAND"
        else:
            element_type = "COMMAND"
        
        element = ParsedElement(
            element_type=element_type,
            value=command_text,
            line_number=self.current_line_num,
            raw_line=node.text.strip()
        )
        self.parsed_elements.append(element)

    def generic_visit(self, node, visited_children):
        """Default visitor for unhandled nodes."""
        return visited_children


class ParserAgent(BaseAgent):
    """
    The Parser Agent is responsible for converting raw script content
    into structured elements and extracting user commands using a PEG grammar.
    """
    
    # PEG Grammar for Slurm scripts
    # We parse line-by-line to ensure robustness against complex shell syntax 
    # that might confuse a full-file grammar without a complete shell definition.
    SLURM_GRAMMAR = r"""
        script          = line*
        line            = (sbatch / agent_comment / comment / command / empty) newline?
        
        sbatch          = ws "#SBATCH" ws (option_value / option_flag) (ws comment_text)?
        option_value    = option_key (ws "=" / ws) ws option_val
        option_flag     = option_key
        option_key      = ~r"-{1,2}[a-zA-Z0-9_-]+"
        option_val      = ~r"[^\s#]+"
        
        agent_comment   = ws "#" ws "Agent SLURM:" ws message
        message         = ~r"[^\n]+"
        
        comment         = ws "#" comment_text
        comment_text    = ~r"[^\n]*"
        
        command         = ws ~r"[^#\n]+" (ws comment)?
        
        empty           = ws
        
        ws              = ~r"[ \t]*"
        newline         = ~r"[\n\r]+"
    """

    def __init__(self):
        super().__init__(agent_id="Parser Agent")
        self.grammar = Grammar(self.SLURM_GRAMMAR)
    
    def run(self, context: JobContext) -> JobContext:
        """
        Parse the raw script into structured elements.
        
        Args:
            context: The JobContext containing the raw script
            
        Returns:
            The updated JobContext with parsed elements
        """
        self.log_trace(context, "Starting parsing with Parsimonious", {"script_length": len(context.raw_script)})
        
        visitor = SlurmScriptVisitor()
        
        try:
            # We append a newline to ensure the last line is processed if it lacks one
            script_to_parse = context.raw_script
            if not script_to_parse.endswith('\n'):
                script_to_parse += '\n'
                
            tree = self.grammar.parse(script_to_parse)
            visitor.visit(tree)
            
            context.parsed_elements = visitor.parsed_elements
            context.user_commands = visitor.user_commands
            
        except ParseError as e:
            self.log_trace(context, "Parsing failed, falling back to regex", {"error": str(e)})
            print(f"Warning: PEG parsing failed at {e}. Falling back to regex.")
            # Fallback to simple regex if grammar fails (e.g., binary characters or crazy syntax)
            self._fallback_regex_parse(context)
            
        self.log_trace(context, "Parsing completed", {
            "parsed_elements": len(context.parsed_elements),
            "user_commands": len(context.user_commands)
        })
        
        return context

    def _fallback_regex_parse(self, context: JobContext):
        """Legacy regex parsing as a safety net."""
        sbatch_pattern = re.compile(r'^\s*#SBATCH\s+([-\w]+)(?:\s+(.+?))?(?:\s*#.*)?$')
        agent_comment_pattern = re.compile(r'^\s*#\s*Agent SLURM:\s*(.+)$', re.IGNORECASE)
        command_pattern = re.compile(r'^\s*([^#\n].*)$')
        
        lines = context.raw_script.split('\n')
        context.parsed_elements = []
        context.user_commands = []
        
        for line_num, line in enumerate(lines, start=1):
            sbatch_match = sbatch_pattern.match(line)
            if sbatch_match:
                context.parsed_elements.append(ParsedElement(
                    element_type="SBATCH",
                    key=sbatch_match.group(1),
                    value=sbatch_match.group(2),
                    line_number=line_num,
                    raw_line=line
                ))
                continue
            
            agent_match = agent_comment_pattern.match(line)
            if agent_match:
                context.user_commands.append(UserCommand(
                    message=agent_match.group(1).strip(),
                    line_number=line_num
                ))
                continue
            
            cmd_match = command_pattern.match(line)
            if cmd_match and cmd_match.group(1).strip():
                command_text = cmd_match.group(1).strip()
                if command_text.startswith('lfs'):
                    etype = "LUSTRE_COMMAND"
                elif any(t in command_text for t in ['bwa', 'gatk', 'samtools', 'fastqc']):
                    etype = "TOOL_COMMAND"
                else:
                    etype = "COMMAND"
                
                context.parsed_elements.append(ParsedElement(
                    element_type=etype,
                    value=command_text,
                    line_number=line_num,
                    raw_line=line
                ))