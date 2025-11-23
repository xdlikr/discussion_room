# 💹 Opinion Room - AI多智能体讨论平台

一个基于AI的多智能体讨论平台，让不同角色的AI分析师针对投资话题进行深度讨论。

## 功能特点

- 🎯 **多智能体讨论** - 多个AI分析师从不同角度分析问题
- ✏️ **可自定义提示词** - 每个Agent的系统提示词可在网页中实时修改
- 🤖 **多模型支持** - 为每个Agent选择不同的AI模型（DeepSeek、Qwen、Kimi等）
- 💬 **ChatGPT风格界面** - 现代化、简洁的对话界面
- 📊 **多轮讨论** - 支持多轮对话，逐步深入分析
- 📝 **智能总结** - 自动生成讨论总结
- 💾 **本地存储** - 使用SQLite保存所有数据

## 技术栈

- **后端**: Python FastAPI
- **前端**: HTML/CSS/JavaScript
- **数据库**: SQLite
- **AI API**: SILICONFLOW

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的API密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 SILICONFLOW_API_KEY。

### 3. 启动服务

```bash
cd backend
python main.py
```

### 4. 访问应用

在浏览器中打开：http://localhost:8000

## 使用说明

1. **创建Agent**: 在左侧面板点击"添加Agent"，输入名称、角色和系统提示词
2. **开始讨论**: 在右侧输入投资话题，点击"开始讨论"
3. **查看分析**: AI分析师们会依次发表观点
4. **多轮讨论**: 可以继续提问，Agent们会基于之前的对话继续分析
5. **查看总结**: 讨论结束后会自动生成智能总结

## 项目结构

```
opinionRoom/
├── backend/           # 后端代码
│   ├── main.py       # FastAPI主应用
│   ├── database.py   # 数据库模型
│   ├── models.py     # Pydantic模型
│   ├── agent_service.py
│   ├── discussion_service.py
│   └── ai_client.py
├── frontend/         # 前端代码
│   ├── index.html
│   ├── css/
│   └── js/
└── requirements.txt
```

## 开发

本项目采用北欧简约设计风格，注重用户体验和代码质量。

## License

MIT
