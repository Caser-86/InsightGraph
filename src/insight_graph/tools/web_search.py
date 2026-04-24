from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "mock"
