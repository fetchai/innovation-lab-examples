"""
The Monitoring Layer: Plugins

This module implements monitoring and audit logging for security events.
Plugins provide observability into agent behavior, tool usage, and security events.

Security Monitoring:
- Track agent invocations per user/role
- Monitor tool usage patterns
- Audit security events
- Performance metrics
"""

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.plugins.base_plugin import BasePlugin
import logging

logger = logging.getLogger(__name__)


class CountInvocationPlugin(BasePlugin):
    """
    A security monitoring plugin that tracks agent and tool invocations.
    
    This plugin provides audit logging for security compliance:
    - Track who is using the agent (user_id, role)
    - Monitor tool invocations
    - Log security events
    - Performance metrics
    """
    
    def __init__(self) -> None:
        """Initialize the plugin with counters and logging."""
        super().__init__(name="security_monitoring_plugin")
        self.agent_count: int = 0
        self.tool_count: int = 0
        self.llm_request_count: int = 0
    
    async def before_agent_callback(self, *, agent: BaseAgent, callback_context: CallbackContext) -> None:
        """
        Monitor agent invocations for security auditing.
        
        This runs before each agent execution to log:
        - User identity (if available in state)
        - Agent invocation count
        - Security events
        """
        self.agent_count += 1
        
        # Try to get user information from state for audit logging
        user_info = {}
        if callback_context.state:
            user_info = {
                "user_role": callback_context.state.get("user_role", "unknown"),
                "user_id": callback_context.state.get("user_id", "unknown"),
            }
        
        # Log security event
        logger.info(
            f"[Security Plugin] Agent invocation #{self.agent_count} - "
            f"User: {user_info.get('user_id', 'unknown')} "
            f"Role: {user_info.get('user_role', 'unknown')}"
        )
        
        # In production, send to SIEM or security monitoring system
        # Example: send_to_security_monitoring(user_info, invocation_count)
