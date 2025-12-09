from abc import ABC, abstractmethod
from typing import Any
from agentSlurm.models.job_context import JobContext


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    All agents should inherit from this class and implement the run method.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @abstractmethod
    def run(self, context: JobContext) -> JobContext:
        """
        Execute the agent's logic on the provided context.

        Args:
            context: The JobContext object containing all relevant data

        Returns:
            The modified JobContext object
        """
        pass

    def log_trace(self, context: JobContext, operation: str, details: Any = None):
        """
        Log a trace entry for debugging and evaluation purposes.

        Args:
            context: The JobContext to add the trace to
            operation: Description of the operation being performed
            details: Additional details about the operation
        """
        trace_entry = {
            "agent_id": self.agent_id,
            "operation": operation,
            "details": details,
        }
        context.trace_log.append(trace_entry)
