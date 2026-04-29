import sqlite3
import json
import logging
from typing import List, Dict, Any
from openai import OpenAI

# ==========================================
# 0. 基础配置与日志设置
# ==========================================
# 设置工业级日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 请替换为你的实际 API KEY
API_KEY = "your-api-key-here"
MODEL_NAME = "gpt-4o-mini" # 或 deepseek-chat 等支持 Function Calling 的模型

# ==========================================
# 1. 数据库管理模块 (模拟企业数据仓库)
# ==========================================
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(':memory:')
        self._init_complex_database()

    def _init_complex_database(self):
        """初始化一��包含多表关联的复杂业务数据库"""
        cursor = self.conn.cursor()
        
        # 1. 部门表
        cursor.execute('CREATE TABLE departments (dept_id INTEGER PRIMARY KEY, dept_name TEXT NOT NULL)')
        # 2. 员工表
        cursor.execute('''CREATE TABLE employees (
            emp_id INTEGER PRIMARY KEY, emp_name TEXT, dept_id INTEGER, 
            FOREIGN KEY(dept_id) REFERENCES departments(dept_id))''')
        # 3. 产品表
        cursor.execute('CREATE TABLE products (prod_id INTEGER PRIMARY KEY, prod_name TEXT, category TEXT, price REAL)')
        # 4. 订单明细表
        cursor.execute('''CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY, emp_id INTEGER, prod_id INTEGER, 
            quantity INTEGER, order_date TEXT,
            FOREIGN KEY(emp_id) REFERENCES employees(emp_id),
            FOREIGN KEY(prod_id) REFERENCES products(prod_id))''')

        # 插入模拟数据
        cursor.executemany('INSERT INTO departments VALUES (?, ?)', [(1, '华东大区'), (2, '华南大区')])
        cursor.executemany('INSERT INTO employees VALUES (?, ?, ?)', [(101, '张总监', 1), (102, '李销售', 1), (103, '王销售', 2)])
        cursor.executemany('INSERT INTO products VALUES (?, ?, ?, ?)', [
            (1001, '企业版SaaS', '软件', 50000.0), (1002, '云服务器', '硬件', 10000.0), (1003, '实施服务', '服务', 20000.0)
        ])
        cursor.executemany('INSERT INTO orders VALUES (?, ?, ?, ?, ?)', [
            (501, 102, 1001, 2, '2023-10-15'), (502, 102, 1003, 1, '2023-10-16'),
            (503, 103, 1002, 5, '2023-11-01'), (504, 101, 1001, 1, '2023-11-05')
        ])
        self.conn.commit()
        logger.info("企业级多表内存数据库初始化完成 (4张表)。")

    def get_database_schema(self) -> str:
        """动态获取数据库DDL，用于RAG注入大模型上下文"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        schemas = [row[0] for row in cursor.fetchall() if row[0]]
        return "\n".join(schemas)

    def execute_query(self, query: str) -> Dict[str, Any]:
        """安全执行SQL并捕获异常"""
        logger.info(f"正在执行 SQL: \n{query}")
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            logger.info(f"SQL 执行成功，返回 {len(results)} 条数据。")
            return {"status": "success", "columns": columns, "data": results}
        except Exception as e:
            error_msg = f"SQL 语法或逻辑错误: {str(e)}"
            logger.warning(f"触发容错机制，捕获到错误: {error_msg}")
            return {"status": "error", "message": error_msg}


# ==========================================
# 2. 核心智能体模块 (长链推理与反思机制)
# ==========================================
class EnterpriseDataAgent:
    def __init__(self, db_manager: DatabaseManager):
        self.client = OpenAI(api_key=API_KEY)
        self.db = db_manager
        self.total_tokens_used = 0 # 追踪 Token 消耗

    def _get_tools_definition(self) -> List[Dict]:
        """定义供模型调用的 Function / Tool"""
        return [{
            "type": "function",
            "function": {
                "name": "execute_sql_in_db",
                "description": "在企业数据库中执行查询 SQL 语句。如果报错，请阅读报错信息并修正 SQL。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {"type": "string", "description": "符合 SQLite 语法的 SQL 语句"}
                    },
                    "required": ["sql_query"],
                }
            }
        }]

    def run_analysis(self, user_intent: str, max_steps: int = 4) -> str:
        """核心 ReAct 工作流：思考 -> 行动 -> 观察 -> 反思"""
        logger.info(f"========== 收到业务查询需求 ==========")
        logger.info(f"需求内容: '{user_intent}'")
        
        # 1. 动态获取 Schema，构建 System Prompt (轻量级 RAG)
        schema_ddl = self.db.get_database_schema()
        system_prompt = f"""你是一个顶级的企业数据分析 Agent。你的任务是将用户的需求转化为 SQL 并执行获取结果，最终输出业务总结报告。
当前数据库包含多张关联表，Schema 如下：
{schema_ddl}

【核心指令】：
1. 思考所需的表关联 (JOIN)，生成严谨的 SQL。
2. 使用 `execute_sql_in_db` 工具执行。
3. [极其重要] 如果工具返回 status 为 "error"，说明你的 SQL 有误（如字段不存在、语法错误）。你必须反思报错原因，修改 SQL 后重新调用工具！
4. 拿到正确数据后，请给出专业、清晰的���据总结。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_intent}
        ]
        
        tools = self._get_tools_definition()

        # 2. 长链推理与自我纠错循环 (The Self-Correction Loop)
        for step in range(1, max_steps + 1):
            logger.info(f"--- 🧠 开启第 {step} 轮模型推理 ---")
            
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.1 # 降低温度以保证 SQL 生成的严谨性
            )
            
            # 记录 Token 消耗
            step_tokens = response.usage.total_tokens
            self.total_tokens_used += step_tokens
            logger.info(f"本轮消耗 Token: {step_tokens} (累计: {self.total_tokens_used})")

            ai_message = response.choices[0].message
            messages.append(ai_message)

            # 分支 A：模型决定调用工具执行 SQL
            if ai_message.tool_calls:
                for tool_call in ai_message.tool_calls:
                    if tool_call.function.name == "execute_sql_in_db":
                        args = json.loads(tool_call.function.arguments)
                        sql_query = args.get("sql_query")
                        
                        # 执行数据库查询
                        db_result = self.db.execute_query(sql_query)
                        
                        # 将结果（数据或错误日志）塞回上下文，闭环反馈给大模型
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": "execute_sql_in_db",
                            "content": json.dumps(db_result, ensure_ascii=False),
                        })
                # 继续下一轮循环，让模型根据 tool 的结果进行决策
                continue 

            # 分支 B：模型认为已经拿到数据，直接输出最终总结
            else:
                logger.info(f"✅ Agent 成功得出结论，任务闭环。")
                return ai_message.content

        logger.error("❌ 达到最大推理步数，无法完成任务。")
        return "很抱歉，数据查询逻辑过于复杂，已超出最大自我纠错次数，请联系数据开发人员介入。"


# ==========================================
# 3. 业务场景测试 (演示长链推理与容错)
# ==========================================
if __name__ == "__main__":
    db = DatabaseManager()
    agent = EnterpriseDataAgent(db_manager=db)

    print("\n" + "="*50)
    print("场景 1：复杂的多表关联查询 (一次性成功)")
    print("="*50)
    report1 = agent.run_analysis("请帮我计算一下各个大区（部门）在2023年的总销售金额是多少？按金额降序排列。")
    print(f"\n[📊 最终报告1]:\n{report1}\n")

    print("\n" + "="*50)
    print("场景 2：故意制造陷阱测试『自我纠错(Self-Correction)』能力")
    print("="*50)
    # 故意问"产品分类"，模型第一次大概率会写 SELECT type，但数据库里叫 category，触发报错纠错闭环
    report2 = agent.run_analysis("请统计一下不同软件和硬件类型的总销量和总销售额。")
    print(f"\n[📊 最终报告2]:\n{report2}\n")
    
    print(f"\n📈 本次测试总计产生 Token 消耗: {agent.total_tokens_used} tokens.")
