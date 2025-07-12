import logging
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import (
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils import new_task, new_agent_text_message, new_text_artifact
from agent import YoutubeSummarizerAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SummarizerAgentExecutor(AgentExecutor):
    """A YouTube Summarizer agent executor."""
    def __init__(self):
        self.agent = YoutubeSummarizerAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        task = context.current_task
        if not task and context.message:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        
        if not task:
            logger.error("No task available for execution")
            return

        async for item in self.agent.stream(query, task.contextId):
            is_task_complete = item['is_task_complete']
            require_user_input = item['require_user_input']
            content = item['content']
            logger.info(
                f'Stream item received: complete={is_task_complete}, require_input={require_user_input}, content_len={len(content)}'
            )
            if not is_task_complete and not require_user_input:
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        status=TaskStatus(
                            state=TaskState.working,
                            message=new_agent_text_message(content, task.contextId, task.id),
                        ),
                        final=False,
                        contextId=task.contextId,
                        taskId=task.id,
                    )
                )
            elif require_user_input:
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        status=TaskStatus(
                            state=TaskState.input_required,
                            message=new_agent_text_message(content, task.contextId, task.id),
                        ),
                        final=True,
                        contextId=task.contextId,
                        taskId=task.id,
                    )
                )
            else:
                await event_queue.enqueue_event(
                    TaskArtifactUpdateEvent(
                        append=False,
                        contextId=task.contextId,
                        taskId=task.id,
                        lastChunk=True,
                        artifact=new_text_artifact(
                            name='video_summary',
                            description='Summary of the YouTube video.',
                            text=content,
                        ),
                    )
                )
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        status=TaskStatus(state=TaskState.completed),
                        final=True,
                        contextId=task.contextId,
                        taskId=task.id,
                    )
                )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception('cancel not supported')