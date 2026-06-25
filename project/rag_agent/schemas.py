from typing import List
from pydantic import BaseModel, Field

class QueryAnalysis(BaseModel):
    is_clear: bool = Field(
        description="指示用户的问题是否清晰且可回答。"
    )
    questions: List[str] = Field(
        description="重写的、自包含的问题列表。"
    )
    clarification_needed: str = Field(
        description="在问题不清晰时所需的澄清说明。"
    )
    is_retrieval_needed: bool = Field(
        default=True,
        description="是否需要检索外部知识库。如果用户在进行纯聊天、问候、或者询问关于对话历史上下文的问题（如“我刚才说了什么”、“我刚才关注的重点是什么”等），应为 false；如果是要查询知识库中关于Java、Spring、微服务、高可用等专业技术知识，应为 true。"
    )