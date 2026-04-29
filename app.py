from flask import Flask, render_template, request, jsonify
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from enterprise_data_agent import DatabaseManager, EnterpriseDataAgent, Config

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 全局Agent实例
db_manager = DatabaseManager()
agent = EnterpriseDataAgent(db_manager)

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/query', methods=['POST'])
def query():
    """处理数据分析查询"""
    data = request.json
    user_query = data.get('query', '')
    
    if not user_query:
        return jsonify({"error": "查询内容不能为空"}), 400
    
    try:
        result = agent.run_analysis(user_query, max_steps=4)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "result": f"错误: {str(e)}"
        }), 500

@app.route('/api/schema', methods=['GET'])
def get_schema():
    """获取数据库Schema"""
    schema = db_manager.get_database_schema()
    return jsonify({
        "schema": schema
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    return jsonify({
        "total_tokens": agent.total_tokens_used,
        "query_count": len(agent.query_history),
        "history": agent.query_history[-10:]  # 最后10条查询
    })

@app.route('/api/examples', methods=['GET'])
def get_examples():
    """获取查询示例"""
    examples = [
        "请帮我计算一下各个大区（部门）在2023年的总销售金额是多少？按金额降序排列。",
        "请统计一下不同软件和硬件类型的总销量和总销售额。",
        "哪个销售员工的业绩最好？请计算每个员工的总销售额。",
        "请列出产品库存少于100的所有产品。",
        "统计各部门员工数和平均薪资。"
    ]
    return jsonify({"examples": examples})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
