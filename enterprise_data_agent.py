import sqlite3
import json
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from openai import OpenAI
from functools import lru_cache
import hashlib

# ==========================================
# 0. 配置管理与日志设置
# ==========================================
class Config:
    """配置管理类"""
    API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
    MAX_CACHE_SIZE = 100
    LOG_LEVEL = logging.INFO

# 设置工业级日志格式
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==========================================
# 1. 数据库管理模块 (企业数据仓库)
# ==========================================
class DatabaseManager:
    """数据库管理类 - 支持SQLite内存数据库"""
    
    def __init__(self):
        self.conn = sqlite3.connect(':memory:')
        self._init_complex_database()
        self._query_cache = {}
        logger.info("数据库管理器初始化完成")

    def _init_complex_database(self):
        """初始化一个包含多表关联的复杂业务数据库"""
        cursor = self.conn.cursor()
        
        # 1. 部门表
        cursor.execute('CREATE TABLE departments (dept_id INTEGER PRIMARY KEY, dept_name TEXT NOT NULL)')
        # 2. 员工表
        cursor.execute('''CREATE TABLE employees (
            emp_id INTEGER PRIMARY KEY, emp_name TEXT, dept_id INTEGER, salary REAL,
            FOREIGN KEY(dept_id) REFERENCES departments(dept_id))''')
        # 3. 产品表
        cursor.execute('CREATE TABLE products (prod_id INTEGER PRIMARY KEY, prod_name TEXT, category TEXT, price REAL, stock INTEGER)')
        # 4. 订单明细表
        cursor.execute('''CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY, emp_id INTEGER, prod_id INTEGER, 
            quantity INTEGER, order_date TEXT, order_amount REAL,
            FOREIGN KEY(emp_id) REFERENCES employees(emp_id),
            FOREIGN KEY(prod_id) REFERENCES products(prod_id))''')
        # 5. 客户表
        cursor.execute('''CREATE TABLE customers (
            cust_id INTEGER PRIMARY KEY, cust_name TEXT, region TEXT, level TEXT)''')

        # 插入模拟数据
        cursor.executemany('INSERT INTO departments VALUES (?, ?)', 
                          [(1, '华东大区'), (2, '华南大区'), (3, '华北大区')])
        cursor.executemany('INSERT INTO employees VALUES (?, ?, ?, ?)', 
                          [(101, '张总监', 1, 25000), (102, '李销售', 1, 15000), 
                           (103, '王销售', 2, 15000), (104, '赵经理', 3, 20000)])
        cursor.executemany('INSERT INTO products VALUES (?, ?, ?, ?, ?)', [
            (1001, '企业版SaaS', '软件', 50000.0, 100), 
            (1002, '云服务器', '硬件', 10000.0, 50), 
            (1003, '实施服务', '服务', 20000.0, 999),
            (1004, '数据分析工具', '软件', 35000.0, 75)
        ])
        cursor.executemany('INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)', [
            (501, 102, 1001, 2, '2023-10-15', 100000), 
            (502, 102, 1003, 1, '2023-10-16', 20000),
            (503, 103, 1002, 5, '2023-11-01', 50000), 
            (504, 101, 1001, 1, '2023-11-05', 50000),
            (505, 104, 1004, 3, '2023-11-10', 105000),
            (506, 103, 1001, 1, '2023-12-01', 50000)
        ])
        cursor.executemany('INSERT INTO customers VALUES (?, ?, ?, ?)', [
            (1, '阿里巴巴', '华东', 'VIP'),
            (2, '腾讯', '华南', 'VIP'),
            (3, '百度', '华北', '普通'),
            (4, '字节跳动', '华东', 'VIP')
        ])
        self.conn.commit()
        logger.info("企业级多表内存数据库初始化完成 (5张表)。")

    def get_database_schema(self) -> str:
        """动态获取数据库DDL"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        schemas = [row[0] for row in cursor.fetchall() if row[0]]
        return "\n".join(schemas)

    def _get_cache_key(self, query: str) -> str:
        """生成查询缓存键"""
        return hashlib.md5(query.encode()).hexdigest()

    def execute_query(self, query: str, use_cache: bool = True) -> Dict[str, Any]:
        """执行SQL查询，支持缓存"""
        cache_key = self._get_cache_key(query)
        
        # 检查缓存
        if use_cache and cache_key in self._query_cache:
            logger.info(f"✅ 命中缓存，返回缓存结果")
            return self._query_cache[cache_key]
        
        logger.info(f"正在执行 SQL: \n{query}")
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            logger.info(f"SQL 执行成功，返回 {len(results)} 条数据。")
            
            result = {"status": "success", "columns": columns, "data": results, "cached": False}
            
            # 存入缓存
            if len(self._query_cache) < Config.MAX_CACHE_SIZE:
                self._query_cache[cache_key] = result
            
            return result
        except Exception as e:
            error_msg = f"SQL 语法或逻辑错误: {str(e)}"
            logger.warning(f"触发容错机制，捕获到错误: {error_msg}")
            return {"status": "error", "message": error_msg}


# ==========================================
# 2. 核心智能体模块 (长链推理与反思机制)
# ==========================================
class EnterpriseDataAgent:
    """企业数据分析Agent - 支持ReAct模式和自我纠错"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.client = OpenAI(api_key=Config.API_KEY)
        self.db = db_manager
        self.total_tokens_used = 0
        self.query_history = []  # 查询历史记录
        logger.info("EnterpriseDataAgent 初始化完成")

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

    def run_analysis(self, user_intent: str, max_steps: int = 4) -> Dict[str, Any]:
        """核心 ReAct 工作流：思考 -> 行动 -> 观察 -> 反思"""
        logger.info(f"========== 收到业务查询需求 ==========")
        logger.info(f"需求内容: '{user_intent}'")
        
        start_time = datetime.now()
        
        # 1. 动态获取 Schema，构建 System Prompt (轻量级 RAG)
        schema_ddl = self.db.get_database_schema()
        system_prompt = f"""你是一个顶级的企业数据分析 Agent。你的任务是将用户的需求转化为 SQL 并执行获取结果，最终输出业务总结报告。
当前数据库包含多张关联表，Schema 如下：
{schema_ddl}

【核心指令】：
1. 思考所需的表关联 (JOIN)，生成严谨的 SQL。
2. 使用 `execute_sql_in_db` 工具执行。
3. [极其重要] 如果工具返回 status 为 "error"，说明你的 SQL 有误（如字段不存在、语法错误）。你必须反思报错原因，修改 SQL 后重新调用工具！
4. 拿到正确数据后，请给出专业、清晰的数据总结。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_intent}
        ]
        
        tools = self._get_tools_definition()
        final_result = None
        execution_steps = []

        # 2. 长链推理与自我纠错循环
        for step in range(1, max_steps + 1):
            logger.info(f"--- 🧠 开启第 {step} 轮模型推理 ---")
            
            try:
                response = self.client.chat.completions.create(
                    model=Config.MODEL_NAME,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.1
                )
                
                # 记录 Token 消耗
                step_tokens = response.usage.total_tokens
                self.total_tokens_used += step_tokens
                logger.info(f"本轮消耗 Token: {step_tokens} (累计: {self.total_tokens_used})")

                ai_message = response.choices[0].message
                messages.append(ai_message)
                execution_steps.append(f"步骤 {step}: 推理完成，Token 使用 {step_tokens}")

                # 分支 A：模型决定调用工具执行 SQL
                if ai_message.tool_calls:
                    for tool_call in ai_message.tool_calls:
                        if tool_call.function.name == "execute_sql_in_db":
                            args = json.loads(tool_call.function.arguments)
                            sql_query = args.get("sql_query")
                            
                            # 执行数据库查询
                            db_result = self.db.execute_query(sql_query)
                            execution_steps.append(f"执行 SQL: {sql_query[:50]}...")
                            
                            # 将结果塞回上下文
                            messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": "execute_sql_in_db",
                                "content": json.dumps(db_result, ensure_ascii=False),
                            })
                    continue 

                # 分支 B：模型认为已经拿到数据，直接输出最终总结
                else:
                    logger.info(f"✅ Agent 成功得出结论，任务闭环。")
                    final_result = ai_message.content
                    break
                    
            except Exception as e:
                logger.error(f"API调用出错: {str(e)}")
                execution_steps.append(f"步骤 {step}: 错误 - {str(e)}")
                return {
                    "success": False,
                    "result": f"API 调用失败: {str(e)}",
                    "execution_steps": execution_steps,
                    "tokens_used": self.total_tokens_used,
                    "duration": str(datetime.now() - start_time)
                }

        if not final_result:
            logger.error("❌ 达到最大推理步数，无法完成任务。")
            final_result = "很抱歉，数据查询逻辑过于复杂，已超出最大自我纠错次数，请联系数据开发人员介入。"

        # 记录查询历史
        duration = datetime.now() - start_time
        history_entry = {
            "timestamp": start_time.isoformat(),
            "query": user_intent,
            "result": final_result[:200] + "..." if len(final_result) > 200 else final_result,
            "tokens": step_tokens,
            "duration": str(duration)
        }
        self.query_history.append(history_entry)

        return {
            "success": True,
            "result": final_result,
            "execution_steps": execution_steps,
            "tokens_used": self.total_tokens_used,
            "duration": str(duration)
        }
