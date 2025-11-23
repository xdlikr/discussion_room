import httpx
import os
import json
import asyncio
from typing import AsyncGenerator, List, Dict
from dotenv import load_dotenv

load_dotenv()


class SiliconFlowClient:
    # 可用模型列表（根据截图）
    AVAILABLE_MODELS = [
        {"id": "deepseek-ai/DeepSeek-V3.1-Terminus", "name": "DeepSeek-V3.1-Terminus", "provider": "DeepSeek"},
        {"id": "deepseek-ai/DeepSeek-V3.2-Exp", "name": "DeepSeek-V3.2-Exp", "provider": "DeepSeek"},
        {"id": "deepseek-ai/DeepSeek-R1", "name": "DeepSeek-R1", "provider": "DeepSeek"},
        {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek-V3", "provider": "DeepSeek"},
        {"id": "Qwen/Qwen2.5-7B-Instruct", "name": "Qwen2.5-7B-Instruct", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-VL-32B-Instruct", "name": "Qwen3-VL-32B-Instruct", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-VL-32B-Thinking", "name": "Qwen3-VL-32B-Thinking", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-VL-8B-Instruct", "name": "Qwen3-VL-8B-Instruct", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-VL-8B-Thinking", "name": "Qwen3-VL-8B-Thinking", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-VL-30B-A3B-Instruct", "name": "Qwen3-VL-30B-A3B-Instruct", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-VL-30B-A3B-Thinking", "name": "Qwen3-VL-30B-A3B-Thinking", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-VL-235B-A22B-Instruct", "name": "Qwen3-VL-235B-A22B-Instruct", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-VL-235B-A22B-Thinking", "name": "Qwen3-VL-235B-A22B-Thinking", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-Omni-30B-A3B-Instruct", "name": "Qwen3-Omni-30B-A3B-Instruct", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-Omni-30B-A3B-Thinking", "name": "Qwen3-Omni-30B-A3B-Thinking", "provider": "Qwen"},
        {"id": "Qwen/Qwen3-Omni-30B-A3B-Captioner", "name": "Qwen3-Omni-30B-A3B-Captioner", "provider": "Qwen"},
        {"id": "moonshotai/Kimi-K2-Thinking", "name": "Kimi-K2-Thinking", "provider": "Moonshot"},
        {"id": "moonshotai/Kimi-K2-Thinking-Turbo", "name": "Kimi-K2-Thinking-Turbo", "provider": "Moonshot"},
        {"id": "MiniMaxAI/MiniMax-M2", "name": "MiniMax-M2", "provider": "MiniMax"},
        {"id": "zai-org/GLM-4.6", "name": "GLM-4.6", "provider": "ZAI"},
        {"id": "Kwaipilot/KAT-Dev", "name": "KAT-Dev", "provider": "Kwai"},
    ]
    
    def __init__(self):
        self.api_key = os.getenv("SILICONFLOW_API_KEY")
        self.base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        self.default_model = "Qwen/Qwen2.5-7B-Instruct"  # 默认模型
        
        if not self.api_key:
            raise ValueError("SILICONFLOW_API_KEY not found in environment variables")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """非流式对话完成"""
        model_to_use = model or self.default_model
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_to_use,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        max_retries: int = 3
    ) -> AsyncGenerator[str, None]:
        """流式对话完成（带重试机制）"""
        model_to_use = model or self.default_model
        
        for attempt in range(max_retries):
            try:
                content_received = False
                full_content = ""
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model_to_use,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            "stream": True
                        }
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]  # 移除 "data: " 前缀
                                if data_str.strip() == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                    if "choices" in data and len(data["choices"]) > 0:
                                        delta = data["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            content_received = True
                                            full_content += content
                                            yield content
                                except json.JSONDecodeError:
                                    continue
                
                # 检查是否收到内容
                if not content_received or not full_content.strip():
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 指数退避：1s, 2s, 4s
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise ValueError("模型没有返回任何内容")
                
                # 成功，返回
                return
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # 最后一次重试失败，抛出异常
                    raise


# 全局客户端实例
ai_client = SiliconFlowClient()

