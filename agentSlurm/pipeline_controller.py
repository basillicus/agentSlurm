from agentSlurm.agents.parser_agent import ParserAgent
from agentSlurm.agents.lustre_agent import LustreAgent
from agentSlurm.agents.llm_agent import LLMAgent
from agentSlurm.agents.learning_agent import LearningAgent
from agentSlurm.agents.synthesis_agent import SynthesisAgent
from agentSlurm.models.job_context import JobContext, UserProfile
from typing import Optional, Dict, List, Any


class PipelineController:
    """
    Main pipeline controller that orchestrates the execution of agents
    in the correct sequence for the MVP.
    """

    def __init__(self, user_profile: UserProfile = UserProfile.MEDIUM, use_llm: bool = False, llm_config: Optional[Dict[Any, Any]] = None, focus_on: Optional[List[Any]] = None):
        self.user_profile = user_profile
        self.use_llm = use_llm
        self.llm_config = llm_config or {}
        self.focus_on = focus_on or []
        
        self.agents = [ParserAgent(), LustreAgent()]
        
        llm_agent = None
        if use_llm:
            llm_agent = LLMAgent(**self.llm_config)
            self.agents.append(llm_agent)
            self.agents.append(LearningAgent())
        
        self.agents.append(SynthesisAgent(llm_agent=llm_agent, focus_on=self.focus_on))

    def run_pipeline(self, script_content: str, script_path: Optional[str] = None) -> JobContext:
        """
        Execute the full analysis pipeline.

        Args:
            script_content: The content of the SLURM script to analyze
            script_path: Optional path to the script file (for logging)

        Returns:
            The final JobContext with all analysis results
        """
        # Create initial context
        context = JobContext(
            raw_script=script_content,
            user_profile=self.user_profile,
            script_path=script_path,
        )

        print(f"Starting analysis with {len(self.agents)} agents...")

        # Run each agent in sequence
        for agent in self.agents:
            print(f"Running {agent.agent_id}...")
            context = agent.run(context)

        # After pipeline completion, if LLM agent was used, run the learning process
        if self.use_llm:
            self._perform_learning_from_llm_insights(context, script_content)

        print("Analysis pipeline completed.")
        return context

    def _perform_learning_from_llm_insights(self, context: JobContext, script_content: str):
        """
        Perform the learning process to convert LLM insights into deterministic rules.
        """
        try:
            from agentSlurm.agents.llm_agent import LLMAgent
            from agentSlurm.utils.knowledge_base_updater import integrate_learned_rules_from_llm_agent
            
            # Find the LLM agent to get its learned rules
            llm_agent = None
            for agent in self.agents:
                if isinstance(agent, LLMAgent):
                    llm_agent = agent
                    break
            
            if llm_agent:
                print("\n[KNOWLEDGE LEARNING] Converting LLM insights to deterministic rules...")
                integrated_rules = integrate_learned_rules_from_llm_agent(
                    llm_agent=llm_agent,
                    script_content=script_content
                )
                
                if integrated_rules:
                    print(f"[KNOWLEDGE LEARNING] Successfully integrated {len(integrated_rules)} new rules into the knowledge base!")
                    print("[KNOWLEDGE LEARNING] These rules will now be available for future deterministic analysis.")
                else:
                    print("[KNOWLEDGE LEARNING] No new rules were integrated (may need higher confidence or validation).")
            else:
                print("[KNOWLEDGE LEARNING] LLM agent not found in pipeline (this should not happen).")
                
        except ImportError as e:
            print(f"[KNOWLEDGE LEARNING] Could not perform learning: {e}")
        except Exception as e:
            print(f"[KNOWLEDGE LEARNING] Error during learning process: {e}")

