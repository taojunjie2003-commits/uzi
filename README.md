# 企业数据分析 Agent - 演示项目

一个基于 **ReAct 模式** 的企业级数据分析智能体，支持自我纠错、长链推理和多表关联查询。

## 🎯 核心功能

### 1. **智能数据分析 Agent**
- 基于 ReAct (Reasoning + Acting) 模式的推理框架
- 自动生成优化的 SQL 查询语句
- 完整的自我纠错机制（SQL 错误自动修复）
- 支持多步推理和复杂的多表 JOIN 操作

### 2. **企业级数据库**
- SQLite 内存数据库（5张关联表）
- 表结构：部门、员工、产品、订单、客户
- 模拟真实的商业数据场景

### 3. **Web 交互界面**
- 🎨 现代化设计，响应式布局
- 📊 实时统计 Token 消耗和查询历史
- 💡 预置查询示例快速上手
- 📝 完整的执行步骤跟踪

### 4. **性能优化**
- ✅ 查询结果缓存（支持 100+ 条记录）
- ✅ Token 消耗追踪
- ✅ 查询历史记录
- ✅ 环境变量配置

---

## 📦 项目结构

```
uzi/
├── enterprise_data_agent.py    # 核心 Agent 逻辑
├── app.py                       # Flask Web 服务器
├── requirements.txt             # 依赖包
├── templates/
│   └── index.html              # Web UI 界面
└── README.md                   # 文档
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置 API Key

```bash
export OPENAI_API_KEY="your-api-key-here"
export MODEL_NAME="gpt-4o-mini"  # 可选
```

### 3. 启动 Web 服务

```bash
python app.py
```

浏览器访问：**http://localhost:5000**

---

## 💡 使用示例

### 示例 1：多表关联查询
**查询：** 请帮我计算一下各个大区（部门）在2023年的总销售金额是多少？按金额降序排列。

**执行流程：**
```
1. Agent 分析需求 → 识别需要 JOIN 部门表和订单表
2. 生成 SQL → SELECT departments.dept_name, SUM(orders.order_amount) ...
3. 执行查询 → 获取结果
4. 输出总结 → 以专业报告格式展示结果
```

### 示例 2：自我纠错测试
**查询：** 请统计一下不同软件和硬件类型的总销量和总销售额。

**容错机制：**
```
第1次：尝试 SELECT type FROM products → ❌ 错误（字段不存在）
自动纠错：识别错误，改为 SELECT category FROM products
第2次：执行正确的 SQL → ✅ 成功获取结果
```

---

## 🔧 API 文档

### POST /api/query
执行数据分析查询

**请求：**
```json
{
  "query": "请帮我计算各个大区的总销售金额"
}
```

**响应：**
```json
{
  "success": true,
  "result": "根据数据分析，华东大区总销售金额为...",
  "execution_steps": ["步骤 1: 推理完成", "执行 SQL: SELECT..."],
  "tokens_used": 2450,
  "duration": "0:00:15.342"
}
```

### GET /api/schema
获取数据库结构

### GET /api/stats
获取统计信息（Token 消耗、查询历史）

### GET /api/examples
获取查询示例

---

## 📊 数据库表结构

### departments（部门）
```sql
CREATE TABLE departments (
  dept_id INTEGER PRIMARY KEY,
  dept_name TEXT NOT NULL
)
```

### employees（员工）
```sql
CREATE TABLE employees (
  emp_id INTEGER PRIMARY KEY,
  emp_name TEXT,
  dept_id INTEGER,
  salary REAL
)
```

### products（产品）
```sql
CREATE TABLE products (
  prod_id INTEGER PRIMARY KEY,
  prod_name TEXT,
  category TEXT,
  price REAL,
  stock INTEGER
)
```

### orders（订单）
```sql
CREATE TABLE orders (
  order_id INTEGER PRIMARY KEY,
  emp_id INTEGER,
  prod_id INTEGER,
  quantity INTEGER,
  order_date TEXT,
  order_amount REAL
)
```

### customers（客户）
```sql
CREATE TABLE customers (
  cust_id INTEGER PRIMARY KEY,
  cust_name TEXT,
  region TEXT,
  level TEXT
)
```

---

## 🎓 核心技术亮点

### 1. **ReAct 推理框架**
```python
for step in range(max_steps):
    # 思考：模型分析用户需求
    response = client.chat.completions.create(...)
    
    # 行动：调用 SQL 执行工具
    if response.tool_calls:
        result = execute_sql(sql_query)
    
    # 观察：反馈结果给模型
    messages.append(tool_result)
    
    # 反思：模型判断是否完成
```

### 2. **自我纠错机制**
- ✅ 捕获 SQL 执行错误
- ✅ 反馈错误信息给模型
- ✅ 模型自动修改 SQL 重试
- ✅ 最多 4 轮自动纠错

### 3. **轻量级 RAG**
- 动态注入数据库 Schema 到 System Prompt
- 帮助模型理解表结构和关系

### 4. **查询缓存**
- 相同查询结果复用
- 减少 API 调用次数
- 降低成本

---

## 🔐 配置管理

编辑 `enterprise_data_agent.py` 中的 `Config` 类：

```python
class Config:
    API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
    MAX_CACHE_SIZE = 100
    LOG_LEVEL = logging.INFO
```

---

## 📈 性能指标

| 指标 | 说明 |
|------|------|
| **Token 消耗** | 实时追踪每次 API 调用的 Token 使用 |
| **查询历史** | 保留最近 100+ 条查询记录 |
| **缓存命中率** | 相同查询 100% 缓存 |
| **推理步数** | 最多 4 步自动纠错 |
| **响应时间** | 平均 15-30 秒（含 API 调用） |

---

## 🐛 故障排除

### 1. "API Key 无效"
```bash
export OPENAI_API_KEY="sk-..."
```

### 2. "Module not found"
```bash
pip install -r requirements.txt
```

### 3. "端口已被占用"
```bash
python app.py --port 5001
```

---

## 📚 参考资源

- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

---

## 📝 License

MIT

---

## 👨‍💻 作者

taojunjie2003-commits

---

**🎉 开始探索企业数据分析的新方式吧！**