from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Tuple, AsyncGenerator
from pydantic import BaseModel
import json
import asyncio
from database import get_db, Discussion, Message, Agent
from models import (
    DiscussionCreate, DiscussionResponse, DiscussionDetail,
    MessageCreate, MessageResponse
)
from ai_client import ai_client
from data_fetcher import stock_fetcher

router = APIRouter(prefix="/api/discussions", tags=["discussions"])


class AskAgentRequest(BaseModel):
    agent_id: int
    content: str


class DebateRequest(BaseModel):
    rounds: int = 2  # 默认2轮辩论


class EnhanceWithDataRequest(BaseModel):
    symbols: List[str]  # 股票代码列表


# ===== 并行处理辅助函数 =====

async def process_agent_response(
    agent: Agent,
    messages: List[Dict[str, str]],
    discussion_id: int,
    db: AsyncSession
) -> Tuple[int, str, bool]:
    """
    并行处理单个Agent的回复，带模型降级策略
    
    Returns:
        (agent_id, content, success): Agent ID、回复内容、是否成功
    """
    # 模型降级策略：主模型 -> 备用模型 -> 默认模型
    fallback_models = [
        agent.model,  # 主模型
        "deepseek-ai/DeepSeek-V3.2-Exp",  # 备用模型1
        "Qwen/Qwen2.5-7B-Instruct"  # 默认模型
    ]
    
    # 去重，避免重复尝试相同模型
    fallback_models = list(dict.fromkeys(fallback_models))
    
    last_error = None
    for model_to_try in fallback_models:
        try:
            full_content = ""
            async for chunk in ai_client.chat_completion_stream(messages, model=model_to_try):
                full_content += chunk
            
            if not full_content.strip():
                if model_to_try != fallback_models[-1]:  # 不是最后一个模型，继续尝试
                    continue
                return (agent.id, "错误: 模型没有返回内容", False)
            
            # 成功，保存到数据库
            message = Message(
                discussion_id=discussion_id,
                agent_id=agent.id,
                content=full_content,
                message_type="agent"
            )
            db.add(message)
            await db.commit()
            
            return (agent.id, full_content, True)
        except Exception as e:
            last_error = e
            # 如果不是最后一个模型，继续尝试下一个
            if model_to_try != fallback_models[-1]:
                continue
            # 所有模型都失败
            break
    
    # 所有模型都失败，保存错误消息
    error_msg = f"错误: {str(last_error)} (已尝试{len(fallback_models)}个模型)"
    try:
        message = Message(
            discussion_id=discussion_id,
            agent_id=agent.id,
            content=error_msg,
            message_type="agent"
        )
        db.add(message)
        await db.commit()
    except:
        pass
    return (agent.id, error_msg, False)


@router.get("", response_model=List[DiscussionResponse])
async def get_discussions(db: AsyncSession = Depends(get_db)):
    """获取所有讨论"""
    result = await db.execute(
        select(Discussion).order_by(Discussion.created_at.desc())
    )
    discussions = result.scalars().all()
    return discussions


@router.get("/{discussion_id}", response_model=DiscussionDetail)
async def get_discussion(discussion_id: int, db: AsyncSession = Depends(get_db)):
    """获取讨论详情（包含所有消息）"""
    # 获取讨论
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    # 获取消息
    result = await db.execute(
        select(Message, Agent.name)
        .outerjoin(Agent, Message.agent_id == Agent.id)
        .where(Message.discussion_id == discussion_id)
        .order_by(Message.created_at)
    )
    rows = result.all()
    
    messages = []
    for message, agent_name in rows:
        messages.append(MessageResponse(
            id=message.id,
            discussion_id=message.discussion_id,
            agent_id=message.agent_id,
            agent_name=agent_name,
            content=message.content,
            message_type=message.message_type,
            created_at=message.created_at
        ))
    
    return DiscussionDetail(
        discussion=DiscussionResponse.from_orm(discussion),
        messages=messages
    )


@router.post("", response_model=DiscussionResponse, status_code=201)
async def create_discussion(
    discussion_data: DiscussionCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新讨论"""
    discussion = Discussion(
        topic=discussion_data.topic,
        status="in_progress"
    )
    db.add(discussion)
    await db.commit()
    await db.refresh(discussion)
    return discussion


@router.post("/{discussion_id}/start")
async def start_discussion(discussion_id: int, db: AsyncSession = Depends(get_db)):
    """开始讨论 - 并行处理所有Agent回复"""
    # 获取讨论
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    # 获取所有Agent
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    agents = result.scalars().all()
    
    if not agents:
        raise HTTPException(status_code=400, detail="No agents available")
    
    async def generate():
        """并行处理所有Agent的回复，但按顺序输出"""
        # 准备所有Agent的消息上下文
        # 获取之前的对话记录（所有Agent共享）
        result = await db.execute(
            select(Message, Agent.name)
            .outerjoin(Agent, Message.agent_id == Agent.id)
            .where(Message.discussion_id == discussion_id)
            .order_by(Message.created_at)
        )
        previous_messages = result.all()
        
        # 滑动窗口：只保留最近15条
        if len(previous_messages) > 15:
            previous_messages = previous_messages[-15:]
        
        # 为每个Agent构建消息上下文
        agent_messages_map = {}
        for agent in agents:
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": f"讨论主题：{discussion.topic}"}
            ]
            
            if previous_messages:
                context = "\n\n以下是其他分析师的观点：\n"
                for msg, agent_name in previous_messages:
                    if msg.message_type == "agent" and agent_name:
                        context += f"\n【{agent_name}】：{msg.content}\n"
                messages.append({"role": "user", "content": context})
            
            agent_messages_map[agent.id] = messages
        
        # 并行执行所有Agent的回复
        tasks = [
            process_agent_response(agent, agent_messages_map[agent.id], discussion_id, db)
            for agent in agents
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 按Agent顺序输出结果
        for i, agent in enumerate(agents):
            yield f"data: {json.dumps({'type': 'agent_start', 'agent_id': agent.id, 'agent_name': agent.name, 'agent_role': agent.role})}\n\n"
            
            if isinstance(results[i], Exception):
                error_msg = f"错误: {str(results[i])}"
                yield f"data: {json.dumps({'type': 'error', 'message': str(results[i])})}\n\n"
                yield f"data: {json.dumps({'type': 'content', 'content': error_msg})}\n\n"
            else:
                agent_id, content, success = results[i]
                # 流式输出内容（分块以保持流式体验）
                if success:
                    chunk_size = 50
                    for j in range(0, len(content), chunk_size):
                        chunk = content[j:j+chunk_size]
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': content})}\n\n"
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
            
            yield f"data: {json.dumps({'type': 'agent_end', 'agent_id': agent.id})}\n\n"
        
        # 所有Agent发言完毕
        yield f"data: {json.dumps({'type': 'all_done'})}\n\n"
        
        # 自动触发辩论（2轮）- 也使用并行处理
        yield f"data: {json.dumps({'type': 'debate_starting'})}\n\n"
        
        for round_num in range(1, 3):  # 2轮辩论
            yield f"data: {json.dumps({'type': 'round_start', 'round': round_num})}\n\n"
            
            # 获取最新历史消息
            result = await db.execute(
                select(Message, Agent.name)
                .outerjoin(Agent, Message.agent_id == Agent.id)
                .where(Message.discussion_id == discussion_id)
                .order_by(Message.created_at)
            )
            history_messages = result.all()
            
            if len(history_messages) > 15:
                history_messages = history_messages[-15:]
            
            # 为每个Agent构建辩论消息
            debate_tasks = []
            for agent in agents:
                messages = [{"role": "system", "content": agent.system_prompt}]
                messages.append({"role": "user", "content": f"讨论主题：{discussion.topic}"})
                
                for msg, agent_name in history_messages:
                    if msg.message_type == "user":
                        messages.append({"role": "user", "content": msg.content})
                    elif msg.message_type == "agent" and agent_name:
                        if agent_name == agent.name:
                            messages.append({"role": "assistant", "content": f"【你之前的观点】{msg.content}"})
                        else:
                            messages.append({"role": "assistant", "content": f"【{agent_name}的观点】{msg.content}"})
                
                if round_num == 1:
                    debate_prompt = "\n\n请基于其他分析师的观点，进行回应：你可以同意并补充，可以反驳并提出理由，也可以提出新问题。"
                else:
                    debate_prompt = f"\n\n这是第{round_num}轮辩论，请基于之前的讨论继续深入：回应反驳、补充观点或提出新问题。"
                messages.append({"role": "user", "content": debate_prompt})
                
                debate_tasks.append(process_agent_response(agent, messages, discussion_id, db))
            
            # 并行执行辩论轮次
            debate_results = await asyncio.gather(*debate_tasks, return_exceptions=True)
            
            # 按顺序输出辩论结果
            for i, agent in enumerate(agents):
                yield f"data: {json.dumps({'type': 'agent_start', 'agent_id': agent.id, 'agent_name': agent.name, 'agent_role': agent.role, 'round': round_num})}\n\n"
                
                if isinstance(debate_results[i], Exception):
                    error_msg = f"错误: {str(debate_results[i])}"
                    yield f"data: {json.dumps({'type': 'error', 'message': str(debate_results[i])})}\n\n"
                    yield f"data: {json.dumps({'type': 'content', 'content': error_msg})}\n\n"
                else:
                    agent_id, content, success = debate_results[i]
                    chunk_size = 50
                    for j in range(0, len(content), chunk_size):
                        chunk = content[j:j+chunk_size]
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                    if not success:
                        yield f"data: {json.dumps({'type': 'error', 'message': content})}\n\n"
                
                yield f"data: {json.dumps({'type': 'agent_end', 'agent_id': agent.id, 'round': round_num})}\n\n"
            
            yield f"data: {json.dumps({'type': 'round_end', 'round': round_num})}\n\n"
        
        yield f"data: {json.dumps({'type': 'debate_done'})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/{discussion_id}/continue")
async def continue_discussion(
    discussion_id: int,
    message_data: MessageCreate,
    db: AsyncSession = Depends(get_db)
):
    """继续讨论 - 用户追问，Agent们继续回答"""
    # 获取讨论
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    # 保存用户消息
    user_message = Message(
        discussion_id=discussion_id,
        agent_id=None,
        content=message_data.content,
        message_type="user"
    )
    db.add(user_message)
    await db.commit()
    
    # 获取所有Agent
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    agents = result.scalars().all()
    
    if not agents:
        raise HTTPException(status_code=400, detail="No agents available")
    
    async def generate():
        """流式生成所有Agent的回复"""
        for agent in agents:
            # 发送Agent开始标记
            yield f"data: {json.dumps({'type': 'agent_start', 'agent_id': agent.id, 'agent_name': agent.name, 'agent_role': agent.role})}\n\n"
            
            # 构建完整的对话历史
            messages = [{"role": "system", "content": agent.system_prompt}]
            
            # 获取所有历史消息
            result = await db.execute(
                select(Message, Agent.name)
                .outerjoin(Agent, Message.agent_id == Agent.id)
                .where(Message.discussion_id == discussion_id)
                .order_by(Message.created_at)
            )
            history_messages = result.all()
            
            # 滑动窗口：只保留最近30条
            if len(history_messages) > 30:
                history_messages = history_messages[-30:]
            
            # 构建对话上下文
            messages.append({"role": "user", "content": f"讨论主题：{discussion.topic}"})
            
            for msg, agent_name in history_messages:
                if msg.message_type == "user":
                    messages.append({"role": "user", "content": msg.content})
                elif msg.message_type == "agent" and agent_name:
                    # 简化：将其他Agent的观点作为助手回复
                    messages.append({"role": "assistant", "content": f"【{agent_name}的观点】{msg.content}"})
            
            # 流式获取AI回复（使用Agent指定的模型）
            full_content = ""
            try:
                async for chunk in ai_client.chat_completion_stream(messages, model=agent.model):
                    full_content += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                continue
            
            # 保存消息到数据库
            message = Message(
                discussion_id=discussion_id,
                agent_id=agent.id,
                content=full_content,
                message_type="agent"
            )
            db.add(message)
            await db.commit()
            
            # 发送Agent结束标记
            yield f"data: {json.dumps({'type': 'agent_end', 'agent_id': agent.id})}\n\n"
        
        # 所有Agent发言完毕
        yield f"data: {json.dumps({'type': 'all_done'})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/{discussion_id}/summarize")
async def summarize_discussion(discussion_id: int, db: AsyncSession = Depends(get_db)):
    """生成讨论总结"""
    # 获取讨论
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    # 获取所有消息
    result = await db.execute(
        select(Message, Agent.name)
        .outerjoin(Agent, Message.agent_id == Agent.id)
        .where(Message.discussion_id == discussion_id)
        .where(Message.message_type == "agent")
        .order_by(Message.created_at)
    )
    messages = result.all()
    
    if not messages:
        raise HTTPException(status_code=400, detail="No messages to summarize")
    
    # 构建总结提示
    content = f"请总结以下关于「{discussion.topic}」的讨论，提取关键观点、共识和分歧：\n\n"
    for msg, agent_name in messages:
        content += f"【{agent_name}】：{msg.content}\n\n"
    
    summary_prompt = [
        {"role": "system", "content": "你是一个专业的讨论总结助手，擅长提取关键信息和共识。"},
        {"role": "user", "content": content}
    ]
    
    async def generate():
        """流式生成总结"""
        full_summary = ""
        try:
            async for chunk in ai_client.chat_completion_stream(summary_prompt):
                full_summary += chunk
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            
            # 保存总结
            discussion.summary = full_summary
            discussion.status = "completed"
            await db.commit()
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.delete("/{discussion_id}", status_code=204)
async def delete_discussion(discussion_id: int, db: AsyncSession = Depends(get_db)):
    """删除讨论"""
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    await db.delete(discussion)
    await db.commit()
    return None


@router.post("/{discussion_id}/ask-agent")
async def ask_specific_agent(
    discussion_id: int,
    request: AskAgentRequest,
    db: AsyncSession = Depends(get_db)
):
    """向特定Agent提问（@提及功能）"""
    # 获取讨论
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    # 获取指定Agent
    result = await db.execute(
        select(Agent).where(Agent.id == request.agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 保存用户消息
    user_message = Message(
        discussion_id=discussion_id,
        agent_id=None,
        content=f"@{agent.name} {request.content}",
        message_type="user"
    )
    db.add(user_message)
    await db.commit()
    
    async def generate():
        """流式生成特定Agent的回复"""
        # 发送Agent开始标记
        yield f"data: {json.dumps({'type': 'agent_start', 'agent_id': agent.id, 'agent_name': agent.name, 'agent_role': agent.role})}\n\n"
        
        # 构建完整的对话历史
        messages = [{"role": "system", "content": agent.system_prompt}]
        
        # 获取所有历史消息
        result = await db.execute(
            select(Message, Agent.name)
            .outerjoin(Agent, Message.agent_id == Agent.id)
            .where(Message.discussion_id == discussion_id)
            .order_by(Message.created_at)
        )
        history_messages = result.all()
        
        # 滑动窗口：只保留最近15条
        if len(history_messages) > 15:
            history_messages = history_messages[-15:]
        
        # 构建对话上下文
        messages.append({"role": "user", "content": f"讨论主题：{discussion.topic}"})
        
        # 添加历史对话
        for msg, agent_name in history_messages:
            if msg.message_type == "user":
                # 如果是@提及，保留原样
                messages.append({"role": "user", "content": msg.content})
            elif msg.message_type == "agent" and agent_name:
                messages.append({"role": "assistant", "content": f"【{agent_name}的观点】{msg.content}"})
        
        # 添加当前问题
        messages.append({"role": "user", "content": request.content})
        
        # 流式获取AI回复（使用Agent指定的模型）
        full_content = ""
        try:
            async for chunk in ai_client.chat_completion_stream(messages, model=agent.model):
                full_content += chunk
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
        except Exception as e:
            error_msg = f"错误: {str(e)}"
            full_content = error_msg
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        # 保存消息到数据库（即使出错也保存）
        if full_content.strip():
            message = Message(
                discussion_id=discussion_id,
                agent_id=agent.id,
                content=full_content,
                message_type="agent"
            )
            db.add(message)
            await db.commit()
        
        # 发送Agent结束标记
        yield f"data: {json.dumps({'type': 'agent_end', 'agent_id': agent.id})}\n\n"
        yield f"data: {json.dumps({'type': 'all_done'})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/{discussion_id}/debate")
async def start_debate(
    discussion_id: int,
    debate_data: DebateRequest,
    db: AsyncSession = Depends(get_db)
):
    """开始辩论 - Agent基于其他Agent的观点进行多轮讨论"""
    # 获取讨论
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    # 获取所有Agent
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    agents = result.scalars().all()
    
    if not agents:
        raise HTTPException(status_code=400, detail="No agents available")
    
    async def generate():
        """并行生成辩论内容"""
        for round_num in range(1, debate_data.rounds + 1):
            # 发送轮次开始标记
            yield f"data: {json.dumps({'type': 'round_start', 'round': round_num})}\n\n"
            
            # 获取所有历史消息（包括之前的轮次）
            result = await db.execute(
                select(Message, Agent.name)
                .outerjoin(Agent, Message.agent_id == Agent.id)
                .where(Message.discussion_id == discussion_id)
                .order_by(Message.created_at)
            )
            history_messages = result.all()
            
            # 滑动窗口：只保留最近15条
            if len(history_messages) > 15:
                history_messages = history_messages[-15:]
            
            # 为每个Agent构建辩论消息
            debate_tasks = []
            for agent in agents:
                messages = [{"role": "system", "content": agent.system_prompt}]
                messages.append({"role": "user", "content": f"讨论主题：{discussion.topic}"})
                
                for msg, agent_name in history_messages:
                    if msg.message_type == "user":
                        messages.append({"role": "user", "content": msg.content})
                    elif msg.message_type == "agent" and agent_name:
                        if agent_name == agent.name:
                            messages.append({"role": "assistant", "content": f"【你之前的观点】{msg.content}"})
                        else:
                            messages.append({"role": "assistant", "content": f"【{agent_name}的观点】{msg.content}"})
                
                # 添加辩论提示
                if round_num == 1:
                    debate_prompt = "\n\n请基于其他分析师的观点，进行回应：你可以同意并补充，可以反驳并提出理由，也可以提出新问题。"
                else:
                    debate_prompt = f"\n\n这是第{round_num}轮辩论，请基于之前的讨论继续深入：回应反驳、补充观点或提出新问题。"
                messages.append({"role": "user", "content": debate_prompt})
                
                debate_tasks.append(process_agent_response(agent, messages, discussion_id, db))
            
            # 并行执行辩论轮次
            debate_results = await asyncio.gather(*debate_tasks, return_exceptions=True)
            
            # 按顺序输出辩论结果
            for i, agent in enumerate(agents):
                yield f"data: {json.dumps({'type': 'agent_start', 'agent_id': agent.id, 'agent_name': agent.name, 'agent_role': agent.role, 'round': round_num})}\n\n"
                
                if isinstance(debate_results[i], Exception):
                    error_msg = f"错误: {str(debate_results[i])}"
                    yield f"data: {json.dumps({'type': 'error', 'message': str(debate_results[i])})}\n\n"
                    yield f"data: {json.dumps({'type': 'content', 'content': error_msg})}\n\n"
                else:
                    agent_id, content, success = debate_results[i]
                    chunk_size = 50
                    for j in range(0, len(content), chunk_size):
                        chunk = content[j:j+chunk_size]
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                    if not success:
                        yield f"data: {json.dumps({'type': 'error', 'message': content})}\n\n"
                
                yield f"data: {json.dumps({'type': 'agent_end', 'agent_id': agent.id, 'round': round_num})}\n\n"
            
            # 发送轮次结束标记
            yield f"data: {json.dumps({'type': 'round_end', 'round': round_num})}\n\n"
        
        # 所有辩论轮次完毕
        yield f"data: {json.dumps({'type': 'debate_done'})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/{discussion_id}/enhance-with-data")
async def enhance_with_data(
    discussion_id: int,
    request: EnhanceWithDataRequest,
    db: AsyncSession = Depends(get_db)
):
    """基于讨论内容获取实时数据并增强分析（两阶段分析）"""
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    agents = result.scalars().all()
    
    if not agents:
        raise HTTPException(status_code=400, detail="No agents available")
    
    stock_data = await stock_fetcher.get_stock_trends(request.symbols)
    
    async def generate():
        yield f"data: {json.dumps({'type': 'data_loaded', 'symbols': list(stock_data.keys())})}\n\n"
        
        # 获取历史消息
        result = await db.execute(
            select(Message, Agent.name)
            .outerjoin(Agent, Message.agent_id == Agent.id)
            .where(Message.discussion_id == discussion_id)
            .order_by(Message.created_at)
        )
        history_messages = result.all()
        
        if len(history_messages) > 15:
            history_messages = history_messages[-15:]
        
        # 构建数据上下文
        data_context = "\n\n以下是实时股票趋势数据，请基于这些数据验证和调整你的建议：\n\n"
        for symbol, data in stock_data.items():
            data_context += f"**{symbol}**:\n"
            data_context += f"- 当前价格: ${data.get('current_price', 'N/A')}\n"
            if 'trend_1w' in data:
                t = data['trend_1w']
                data_context += f"- 1周趋势: {t['change_percent']:+.2f}% (${t['old_price']:.2f} → ${t['current_price']:.2f})\n"
            if 'trend_1mo' in data:
                t = data['trend_1mo']
                data_context += f"- 1月趋势: {t['change_percent']:+.2f}% (${t['old_price']:.2f} → ${t['current_price']:.2f})\n"
            if 'trend_3mo' in data:
                t = data['trend_3mo']
                data_context += f"- 3月趋势: {t['change_percent']:+.2f}% (${t['old_price']:.2f} → ${t['current_price']:.2f})\n"
            if data.get('rsi'):
                data_context += f"- RSI: {data['rsi']:.2f}\n"
            data_context += "\n"
        
        data_context += "\n请基于以上实时趋势数据，验证和调整你之前的建议。关注趋势（1周/1月/3月），不只是当天价格。"
        
        # 为每个Agent构建消息
        enhance_tasks = []
        for agent in agents:
            messages = [{"role": "system", "content": agent.system_prompt}]
            messages.append({"role": "user", "content": f"讨论主题：{discussion.topic}"})
            
            for msg, agent_name in history_messages:
                if msg.message_type == "user":
                    messages.append({"role": "user", "content": msg.content})
                elif msg.message_type == "agent" and agent_name:
                    messages.append({"role": "assistant", "content": f"【{agent_name}的观点】{msg.content}"})
            
            messages.append({"role": "user", "content": data_context})
            enhance_tasks.append(process_agent_response(agent, messages, discussion_id, db))
        
        # 并行执行数据增强
        enhance_results = await asyncio.gather(*enhance_tasks, return_exceptions=True)
        
        # 按顺序输出结果
        for i, agent in enumerate(agents):
            yield f"data: {json.dumps({'type': 'agent_start', 'agent_id': agent.id, 'agent_name': agent.name, 'agent_role': agent.role})}\n\n"
            
            if isinstance(enhance_results[i], Exception):
                error_msg = f"错误: {str(enhance_results[i])}"
                yield f"data: {json.dumps({'type': 'error', 'message': str(enhance_results[i])})}\n\n"
                yield f"data: {json.dumps({'type': 'content', 'content': error_msg})}\n\n"
            else:
                agent_id, content, success = enhance_results[i]
                chunk_size = 50
                for j in range(0, len(content), chunk_size):
                    chunk = content[j:j+chunk_size]
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                if not success:
                    yield f"data: {json.dumps({'type': 'error', 'message': content})}\n\n"
            
            yield f"data: {json.dumps({'type': 'agent_end', 'agent_id': agent.id})}\n\n"
        
        yield f"data: {json.dumps({'type': 'enhance_done'})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/{discussion_id}/pause")
async def pause_discussion(discussion_id: int, db: AsyncSession = Depends(get_db)):
    """暂停讨论"""
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    discussion.status = "paused"
    await db.commit()
    await db.refresh(discussion)
    
    return {"status": "paused", "discussion_id": discussion_id}


@router.post("/{discussion_id}/resume")
async def resume_discussion(discussion_id: int, db: AsyncSession = Depends(get_db)):
    """继续讨论"""
    result = await db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    )
    discussion = result.scalar_one_or_none()
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    discussion.status = "in_progress"
    await db.commit()
    await db.refresh(discussion)
    
    return {"status": "in_progress", "discussion_id": discussion_id}

