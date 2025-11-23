from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel
from database import get_db, Agent
from models import AgentCreate, AgentUpdate, AgentResponse, ModelInfo
from ai_client import SiliconFlowClient
from init_default_agents import DEFAULT_AGENTS

router = APIRouter(prefix="/api/agents", tags=["agents"])


class BatchUpdateModel(BaseModel):
    agent_ids: List[int]
    model: str


@router.get("/models/available", response_model=List[ModelInfo])
async def get_available_models():
    """获取可用的AI模型列表"""
    return SiliconFlowClient.AVAILABLE_MODELS


@router.get("", response_model=List[AgentResponse])
async def get_agents(db: AsyncSession = Depends(get_db)):
    """获取所有Agent"""
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    agents = result.scalars().all()
    return agents


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个Agent"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(agent_data: AgentCreate, db: AsyncSession = Depends(get_db)):
    """创建新Agent"""
    agent = Agent(
        name=agent_data.name,
        role=agent_data.role,
        system_prompt=agent_data.system_prompt,
        model=agent_data.model or "Qwen/Qwen2.5-7B-Instruct"
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新Agent信息"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 更新非空字段
    if agent_data.name is not None:
        agent.name = agent_data.name
    if agent_data.role is not None:
        agent.role = agent_data.role
    if agent_data.system_prompt is not None:
        agent.system_prompt = agent_data.system_prompt
    if agent_data.model is not None:
        agent.model = agent_data.model
    
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    """删除Agent"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await db.delete(agent)
    await db.commit()
    return None


@router.patch("/batch-update-model", response_model=List[AgentResponse])
async def batch_update_model(
    update_data: BatchUpdateModel,
    db: AsyncSession = Depends(get_db)
):
    """批量更新Agent的模型"""
    if not update_data.agent_ids:
        raise HTTPException(status_code=400, detail="agent_ids cannot be empty")
    
    # 获取所有要更新的Agent
    result = await db.execute(
        select(Agent).where(Agent.id.in_(update_data.agent_ids))
    )
    agents = result.scalars().all()
    
    if len(agents) != len(update_data.agent_ids):
        raise HTTPException(status_code=404, detail="Some agents not found")
    
    # 批量更新模型
    for agent in agents:
        agent.model = update_data.model
    
    await db.commit()
    
    # 刷新并返回
    for agent in agents:
        await db.refresh(agent)
    
    return agents


@router.post("/init-defaults", response_model=List[AgentResponse], status_code=201)
async def init_default_team(db: AsyncSession = Depends(get_db)):
    """加载默认专业Agent团队"""
    # 检查是否已有Agent
    result = await db.execute(select(Agent))
    existing_agents = result.scalars().all()
    
    if existing_agents:
        raise HTTPException(
            status_code=400, 
            detail=f"Database already has {len(existing_agents)} agents. Please delete them first."
        )
    
    # 创建默认Agent
    created_agents = []
    for agent_data in DEFAULT_AGENTS:
        agent = Agent(**agent_data)
        db.add(agent)
        created_agents.append(agent)
    
    await db.commit()
    
    # 刷新所有Agent
    for agent in created_agents:
        await db.refresh(agent)
    
    return created_agents


@router.delete("/all", status_code=204)
async def delete_all_agents(db: AsyncSession = Depends(get_db)):
    """删除所有Agent"""
    result = await db.execute(select(Agent))
    agents = result.scalars().all()
    
    for agent in agents:
        await db.delete(agent)
    
    await db.commit()
    return None

