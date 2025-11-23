from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Agent相关模型
class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=200)
    system_prompt: str = Field(..., min_length=1)
    model: Optional[str] = Field("Qwen/Qwen2.5-7B-Instruct", max_length=200)


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[str] = Field(None, min_length=1, max_length=200)
    system_prompt: Optional[str] = Field(None, min_length=1)
    model: Optional[str] = Field(None, max_length=200)


class AgentResponse(BaseModel):
    id: int
    name: str
    role: str
    system_prompt: str
    model: Optional[str] = "Qwen/Qwen2.5-7B-Instruct"
    created_at: datetime

    class Config:
        from_attributes = True


# AI模型信息
class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str


# Discussion相关模型
class DiscussionCreate(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)


class DiscussionResponse(BaseModel):
    id: int
    topic: str
    status: str
    summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Message相关模型
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    message_type: str = "user"  # user, agent, summary


class MessageResponse(BaseModel):
    id: int
    discussion_id: int
    agent_id: Optional[int] = None
    agent_name: Optional[str] = None
    content: str
    message_type: str
    created_at: datetime

    class Config:
        from_attributes = True


# 讨论详情（包含消息）
class DiscussionDetail(BaseModel):
    discussion: DiscussionResponse
    messages: List[MessageResponse]


# AI响应流式数据
class StreamChunk(BaseModel):
    content: str
    done: bool = False

