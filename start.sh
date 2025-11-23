#!/bin/bash

# Opinion Room 启动脚本

echo "🚀 启动 Opinion Room..."

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到.env文件，正在创建..."
    cp env.example .env
    echo "✅ 已创建.env文件，请编辑并填入你的 SILICONFLOW_API_KEY"
    echo "   然后重新运行此脚本"
    exit 1
fi

# 检查Python依赖
echo "📦 检查依赖..."
pip list | grep -q fastapi
if [ $? -ne 0 ]; then
    echo "⚠️  未找到依赖，正在安装..."
    pip install -r requirements.txt
fi

# 进入backend目录并启动服务
cd backend
echo "✨ 启动服务器..."
python main.py

