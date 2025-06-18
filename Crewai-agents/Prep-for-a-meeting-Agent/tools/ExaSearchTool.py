import os
from typing import List, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from exa_py import Exa

# Singleton pattern for Exa API instance
class ExaAPI:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            api_key = os.environ.get("EXA_API_KEY")
            if not api_key:
                raise ValueError("EXA_API_KEY environment variable not set")
            cls._instance = Exa(api_key=api_key)
        return cls._instance

class SearchSchema(BaseModel):
    query: str = Field(description="The search query to look up")

class ExaSearchTool(BaseTool):
    name: str = "search"
    description: str = "Search for webpages based on the query."
    args_schema: BaseModel = SearchSchema
    
    def _run(self, query: str) -> str:
        try:
            results = ExaAPI.get_instance().search(query, use_autoprompt=True, num_results=3)
            return str(results)
        except Exception as e:
            return f"Error searching: {str(e)}"

class FindSimilarSchema(BaseModel):
    url: str = Field(description="URL to find similar content for")

class ExaFindSimilarTool(BaseTool):
    name: str = "find_similar"
    description: str = "Search for webpages similar to a given URL. The URL should be from a previous search result."
    args_schema: BaseModel = FindSimilarSchema
    
    def _run(self, url: str) -> str:
        try:
            results = ExaAPI.get_instance().find_similar(url, num_results=3)
            return str(results)
        except Exception as e:
            return f"Error finding similar: {str(e)}"

class GetContentsSchema(BaseModel):
    ids: List[str] = Field(description="List of Exa result IDs to retrieve content for")

class ExaGetContentsTool(BaseTool):
    name: str = "get_contents"
    description: str = "Get the contents of webpages. Provide a list of result IDs from a previous search."
    args_schema: BaseModel = GetContentsSchema
    
    def _run(self, ids: List[str]) -> str:
        try:
            # Convert string representation of list to actual list if needed
            if isinstance(ids, str) and ids.startswith('[') and ids.endswith(']'):
                import ast
                ids = ast.literal_eval(ids)
            elif isinstance(ids, str):
                # If a single string ID was passed
                ids = [ids]
                
            results = ExaAPI.get_instance().get_contents(ids)
            
            # Format the results for readability
            formatted_results = []
            if isinstance(results, list):
                for result in results:
                    formatted_results.append(f"URL: {result.url}\nTitle: {result.title}\nContent: {result.text[:1000]}...")
            else:
                # Handle case where a single result is returned
                formatted_results.append(f"URL: {results.url}\nTitle: {results.title}\nContent: {results.text[:1000]}...")
                
            return "\n\n---\n\n".join(formatted_results)
        except Exception as e:
            return f"Error getting contents: {str(e)}"

def tools():
    """Return a list of tool instances for use in agents."""
    return [ExaSearchTool(), ExaFindSimilarTool(), ExaGetContentsTool()]