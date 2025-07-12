import logging
import json
import re
import requests
from typing import AsyncIterable, Any
from autogen import AssistantAgent, LLMConfig
from youtube_transcript_api._api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Hardcoded API key (not recommended for production)

class ResponseModel(BaseModel):
    """Response model for the YouTube Summarizer Agent."""
    text_reply: str
    closed_captions: str | None
    status: str = "TERMINATE"

    def format(self) -> str:
        """Format the response as a string."""
        if self.closed_captions is None:
            return self.text_reply
        return f"{self.text_reply}\n\nClosed Captions:\n{self.closed_captions}"



def get_api_key() -> str:
    """Helper method to handle API Key."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY is not set.")
        raise ValueError("OPENAI_API_KEY is not set")
    return api_key

class YoutubeSummarizerAgent:
    """Agent to summarize YouTube videos using transcripts."""
    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        try:
            llm_config = LLMConfig(
                model='gpt-4o',
                api_key=get_api_key(),
                response_format=ResponseModel,
            )
            self.agent = AssistantAgent(
                name='YoutubeSummarizerAgent',
                llm_config=llm_config,
                system_message=(
                    'You are a specialized assistant for summarizing YouTube videos. '
                    'You receive video transcripts and generate concise summaries. '
                    'If a YouTube URL is provided, summarize the video based on its transcript. '
                    'If no URL is provided or the query is unrelated, '
                    'state that you can only summarize YouTube videos.\n\n'
                    'Always respond using the ResponseModel format:\n'
                    '- text_reply: The video summary or response text\n'
                    '- closed_captions: YouTube captions if available, null if not relevant\n'
                    '- status: Always "TERMINATE"\n\n'
                    'Example response:\n'
                    '{\n'
                    '  "text_reply": "Summary of the video...",\n'
                    '  "closed_captions": null,\n'
                    '  "status": "TERMINATE"\n'
                    '}'
                ),
            )
            self.initialized = True
            logger.info('YouTube Summarizer Agent initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize agent: {e}')
            self.initialized = False

    def extract_video_id(self, url: str) -> str | None:
        """Extract video ID from YouTube URL."""
        pattern = r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)'
        match = re.search(pattern, url)
        return match.group(1) if match else None

    async def get_transcript(self, video_id: str) -> str | None:
        """Fetch transcript for a YouTube video."""
        # Try multiple languages
        languages = ['en', 'en-US', 'en-GB', 'auto']
        
        for lang in languages:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                logger.info(f"Found transcript in language: {lang}")
                return ' '.join([entry['text'] for entry in transcript])
            except NoTranscriptFound:
                logger.debug(f"No transcript found for video ID: {video_id} in language: {lang}")
                continue
            except Exception as e:
                logger.error(f"Error fetching transcript for language {lang}: {e}")
                continue
        
        # Try to get any available transcript
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            logger.info("Found transcript using auto-detection")
            return ' '.join([entry['text'] for entry in transcript])
        except NoTranscriptFound:
            logger.warning(f"No transcript found for video ID: {video_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching transcript: {e}")
            return None

    async def get_video_info(self, video_id: str) -> dict | None:
        """Get basic video information as fallback when transcript is not available."""
        try:
            # This is a simple approach - in production you might want to use YouTube Data API
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Extract title from HTML (simplified)
                title_match = re.search(r'<title>(.*?)</title>', response.text)
                title = title_match.group(1) if title_match else "Unknown Title"
                return {
                    'title': title.replace(' - YouTube', ''),
                    'url': url,
                    'video_id': video_id
                }
        except Exception as e:
            logger.error(f"Error fetching video info: {e}")
        return None

    def get_agent_response(self, response: str) -> dict[str, Any]:
        """Format agent response in a consistent structure."""
        try:
            response_dict = json.loads(response)
            model = ResponseModel(**response_dict)
            return {
                'is_task_complete': True,
                'require_user_input': False,
                'content': model.format(),
            }
        except Exception as e:
            logger.error(f'Error parsing response: {e}, response: {response}')
            return {
                'is_task_complete': True,
                'require_user_input': False,
                'content': response,
            }

    async def stream(self, query: str, sessionId: str) -> AsyncIterable[dict[str, Any]]:
        """Stream updates from the summarizer agent."""
        if not self.initialized:
            yield {
                'is_task_complete': False,
                'require_user_input': True,
                'content': 'Agent initialization failed. Please check the dependencies and logs.',
            }
            return

        yield {
            'is_task_complete': False,
            'require_user_input': False,
            'content': 'Processing video summary request...',
        }
        logger.info(f'Processing query: {query[:50]}...')

        try:
            video_id = self.extract_video_id(query)
            if not video_id:
                response = {
                    'text_reply': 'Please provide a valid YouTube video URL.',
                    'closed_captions': None,
                    'status': 'TERMINATE',
                }
                yield self.get_agent_response(json.dumps(response))
                return

            transcript = await self.get_transcript(video_id)
            if not transcript:
                # Try to get video info as fallback
                video_info = await self.get_video_info(video_id)
                if video_info:
                    response = {
                        'text_reply': f'No transcript available for "{video_info["title"]}" (ID: {video_id}). This could be because:\n• The video has no captions/subtitles\n• The video is private or restricted\n• The video has been removed\n\nPlease try a different YouTube video with available captions.',
                        'closed_captions': None,
                        'status': 'TERMINATE',
                    }
                else:
                    response = {
                        'text_reply': f'No transcript available for this video (ID: {video_id}). This could be because:\n• The video has no captions/subtitles\n• The video is private or restricted\n• The video has been removed\n\nPlease try a different YouTube video with available captions.',
                        'closed_captions': None,
                        'status': 'TERMINATE',
                    }
                yield self.get_agent_response(json.dumps(response))
                return

            # Summarize the transcript
            prompt = (
                f"Summarize the following YouTube video transcript in 100-150 words:\n\n{transcript[:4000]}\n\n"
                "Provide a concise summary of the main points."
            )
            result = await self.agent.a_run(
                message=prompt,
                max_turns=1,
                user_input=False,
            )
            try:
                summary = await result.summary
                response = {
                    'text_reply': summary,
                    'closed_captions': transcript[:1000],  # Limit captions for brevity
                    'status': 'TERMINATE',
                }
                yield self.get_agent_response(json.dumps(response))
            except Exception as e:
                logger.error(f'Error extracting response: {e}')
                yield {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': f'Error processing request: {str(e)}',
                }
        except Exception as e:
            logger.error(f'Error in streaming agent: {e}')
            yield {
                'is_task_complete': False,
                'require_user_input': True,
                'content': f'Error processing request: {str(e)}',
            }