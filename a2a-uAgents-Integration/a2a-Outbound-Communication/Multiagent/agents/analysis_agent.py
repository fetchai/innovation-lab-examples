import json
import requests
from dotenv import load_dotenv
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Part, TextPart
from a2a.utils import new_agent_text_message
from typing_extensions import override

# Load environment variables
load_dotenv()

class AnalysisAgentExecutor(AgentExecutor):
    """Analysis agent that specializes in data analysis and insights generation."""
    
    def __init__(self):
        self.url = "https://api.asi1.ai/v1/chat/completions"
        self.api_key = os.getenv("ASI1_API_KEY")
        self.model = "asi1-mini"
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        self.system_prompt = """You are a Senior Data Analyst AI agent. Your expertise includes:
1. Data analysis and interpretation
2. Statistical analysis and insights
3. Trend identification and forecasting
4. Business intelligence and reporting
5. Data visualization recommendations
6. Performance metrics analysis

Analysis Commands you can handle:
- ANALYZE:[data/topic] - Perform comprehensive analysis
- TRENDS:[data] - Identify trends and patterns
- COMPARE:[item1] vs [item2] - Comparative analysis
- METRICS:[data] - Calculate key metrics
- INSIGHTS:[data] - Generate actionable insights
- FORECAST:[data] - Predict future trends

Always provide structured, data-driven insights with clear recommendations.
        """
    
    @override
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message_content = ""
        for part in context.message.parts:
            if isinstance(part, Part) and isinstance(part.root, TextPart):
                message_content = part.root.text
                break
        
        try:
            # Parse command if it's a structured analysis request
            if message_content.startswith("ANALYZE:"):
                await self._handle_analyze_command(message_content, event_queue)
            elif message_content.startswith("TRENDS:"):
                await self._handle_trends_command(message_content, event_queue)
            elif message_content.startswith("COMPARE:"):
                await self._handle_compare_command(message_content, event_queue)
            elif message_content.startswith("METRICS:"):
                await self._handle_metrics_command(message_content, event_queue)
            elif message_content.startswith("INSIGHTS:"):
                await self._handle_insights_command(message_content, event_queue)
            elif message_content.startswith("FORECAST:"):
                await self._handle_forecast_command(message_content, event_queue)
            else:
                # General analysis request
                await self._handle_general_request(message_content, event_queue)
                
        except Exception as e:
            await event_queue.enqueue_event(
                new_agent_text_message(f"❌ Analysis error: {str(e)}")
            )
    
    async def _handle_analyze_command(self, command: str, event_queue: EventQueue):
        """Handle ANALYZE:data/topic commands."""
        data_or_topic = command.replace("ANALYZE:", "", 1)
        
        prompt = f"Perform a comprehensive analysis of: {data_or_topic}. Include key findings, patterns, and recommendations."
        
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 2000,
            "temperature": 0.3,
            "stream": False
        })
        
        response = requests.post(self.url, headers=self.headers, data=payload)
        response.raise_for_status()
        analysis = response.json()['choices'][0]['message']['content']
        
        formatted_response = f"""📊 Analysis Agent - Comprehensive Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Subject: {data_or_topic}

{analysis}

✅ Analysis completed by AI Senior Data Analyst
        """
        
        await event_queue.enqueue_event(new_agent_text_message(formatted_response))
    
    async def _handle_general_request(self, message_content: str, event_queue: EventQueue):
        """Handle general analysis requests."""
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Analysis Request: {message_content}"}
            ],
            "max_tokens": 1500,
            "temperature": 0.4,
 "stream": False
        })
        
        response = requests.post(self.url, headers=self.headers, data=payload)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        
        formatted_response = f"""📊 Analysis Agent Response
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Request: {message_content}

{content}

✅ Response by AI Senior Data Analyst
        """
        
        await event_queue.enqueue_event(new_agent_text_message(formatted_response))
    
    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(new_agent_text_message("Analysis task cancelled."))
    
    # Placeholder methods for other commands (same structure, omitted for brevity)
    async def _handle_trends_command(self, command: str, event_queue: EventQueue):
        pass
    
    async def _handle_compare_command(self, command: str, event_queue: EventQueue):
        pass
    
    async def _handle_metrics_command(self, command: str, event_queue: EventQueue):
        pass
    
    async def _handle_insights_command(self, command: str, event_queue: EventQueue):
        pass
    
    async def _handle_forecast_command(self, command: str, event_queue: EventQueue):
        pass