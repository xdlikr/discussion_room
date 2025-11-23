@echo off
REM Opinion Room 启动脚本 (Windows)

echo 🚀 启动 Opinion Room...

REM 检查.env文件
if not exist ".env" (
    echo ⚠️  未找到.env文件，正在创建...
    copy env.example .env
    echo ✅ 已创建.env文件，请编辑并填入你的 SILICONFLOW_API_KEY
    echo    然后重新运行此脚本
    pause
    exit /b 1
)

REM 检查Python依赖
echo 📦 检查依赖...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo ⚠️  未找到依赖，正在安装...
    pip install -r requirements.txt
)

REM 进入backend目录并启动服务
cd backend
echo ✨ 启动服务器...
python main.py

