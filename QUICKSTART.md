# 🚀 快速启动指南

## 三步启动

### 1️⃣ 安装依赖

```bash
pip install -r requirements.txt
```

### 2️⃣ 配置API密钥

```bash
# 复制环境变量文件
cp env.example .env

# 编辑 .env 文件，填入你的API密钥
# SILICONFLOW_API_KEY=your_api_key_here
```

### 3️⃣ 启动服务

```bash
cd backend
python main.py
```

然后在浏览器访问：**http://localhost:8000**

---

## 首次使用

### 添加第一个AI分析师

1. 点击左侧的 **"+"** 按钮
2. 填写信息：
   ```
   名称：价值投资者
   角色：专注于长期价值投资
   系统提示词：你是一位经验丰富的价值投资分析师，受沃伦·巴菲特的投资理念启发。你擅长从基本面角度分析投资机会，注重企业的内在价值、护城河和长期增长潜力。
   ```
3. 点击 **"保存"**

### 创建更多分析师

**技术分析师**
```
名称：技术派
角色：技术分析专家
系统提示词：你是一位专业的技术分析师，擅长使用图表和指标分析市场趋势。你关注价格行为、成交量、支撑阻力位等技术信号。
```

**风险评估师**
```
名称：风控专家
角色：风险管理专家
系统提示词：你是一位风险管理专家，擅长识别投资风险。你从风险控制角度评估投资机会，关注各种潜在风险因素。
```

### 开始第一次讨论

1. 在底部输入框输入：**"分析特斯拉当前的投资价值"**
2. 点击 **"开始讨论"**
3. 观看AI分析师们的精彩讨论！

---

## 项目结构

```
opinionRoom/
├── backend/              # 后端代码
│   ├── main.py          # 启动文件
│   ├── database.py      # 数据库
│   ├── models.py        # 数据模型
│   ├── ai_client.py     # AI客户端
│   ├── agent_service.py # Agent API
│   └── discussion_service.py # 讨论API
├── frontend/            # 前端代码
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
└── .env                 # 配置文件（需要创建）
```

---

## 获取SILICONFLOW API密钥

1. 访问：https://siliconflow.cn/
2. 注册/登录账号
3. 进入控制台
4. 创建API密钥
5. 复制密钥到 `.env` 文件

---

## 故障排除

**问题1：端口被占用**
```bash
# 修改 backend/main.py 中的端口号
uvicorn.run("main:app", host="0.0.0.0", port=8001)  # 改为8001
```

**问题2：找不到模块**
```bash
pip install -r requirements.txt
```

**问题3：API密钥错误**
- 检查 `.env` 文件是否存在
- 检查密钥是否正确复制

---

## 更多帮助

- 详细使用指南：[USAGE.md](USAGE.md)
- API文档：http://localhost:8000/docs
- 测试清单：[TEST_CHECKLIST.md](TEST_CHECKLIST.md)

---

**享受多智能体AI讨论的乐趣！** 💹✨

