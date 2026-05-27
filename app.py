"""
AI问答系统 - 后端服务
类似DeepSeek网页版，调用硅基流动API
支持：思考链展示、联网搜索（强力爬虫）
"""
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from openai import OpenAI
import json
import os
from config import API_KEY, BASE_URL, MODEL, AI_PROVIDER
from crawler import sync_web_search

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# 初始化OpenAI兼容客户端（硅基流动兼容OpenAI格式）
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)


# ========== 联网搜索功能（使用强力爬虫） ==========

def web_search(query, max_results=8):
    """
    使用强力爬虫进行多引擎搜索 + 网页内容抓取
    返回搜索结果列表
    """
    try:
        results, _ = sync_web_search(query, max_results)
        return results
    except Exception as e:
        print(f"搜索出错: {e}")
        return []


def build_search_context(query):
    """构建搜索上下文，用于注入到对话中"""
    try:
        results, context = sync_web_search(query)
        return context
    except Exception as e:
        print(f"构建搜索上下文出错: {e}")
        return ""


# ========== 路由 ==========

@app.route('/')
def index():
    """返回前端页面"""
    return send_from_directory('static', 'index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """聊天接口 - 流式响应，支持思考链和联网搜索"""
    data = request.get_json()
    messages = data.get('messages', [])
    enable_search = data.get('enable_search', False)
    
    if not messages:
        return jsonify({'error': '消息不能为空'}), 400
    
    if not API_KEY:
        return jsonify({'error': '请先在config.py中配置API密钥'}), 500
    
    # 如果启用联网搜索，将搜索结果注入到最后一条用户消息
    api_messages = [dict(m) for m in messages]
    
    if enable_search and api_messages:
        # 找到最后一条用户消息
        last_user_msg = None
        for msg in reversed(api_messages):
            if msg['role'] == 'user':
                last_user_msg = msg
                break
        
        if last_user_msg:
            search_context = build_search_context(last_user_msg['content'])
            if search_context:
                last_user_msg['content'] = last_user_msg['content'] + search_context
    
    def generate():
        try:
            # 先发送搜索状态
            if enable_search:
                yield f"data: {json.dumps({'type': 'search_start'})}\n\n"
            
            # 调用硅基流动API（流式）
            response = client.chat.completions.create(
                model=MODEL,
                messages=api_messages,
                stream=True,
                temperature=0.7,
                max_tokens=4096,
            )
            
            if enable_search:
                yield f"data: {json.dumps({'type': 'search_end'})}\n\n"
            
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    # 思考链内容（DeepSeek-R1 模型特有）
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': delta.reasoning_content})}\n\n"
                    
                    # 正式回答内容
                    if delta.content:
                        yield f"data: {json.dumps({'type': 'content', 'content': delta.content})}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            error_msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/search', methods=['POST'])
def search():
    """独立搜索接口"""
    data = request.get_json()
    query = data.get('query', '')
    
    if not query:
        return jsonify({'error': '搜索关键词不能为空'}), 400
    
    results = web_search(query)
    return jsonify({'results': results})


@app.route('/api/models', methods=['GET'])
def get_models():
    """获取当前使用的模型信息"""
    return jsonify({
        'provider': AI_PROVIDER,
        'model': MODEL,
        'base_url': BASE_URL
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 50)
    print("  AI问答系统启动中...")
    print(f"  服务提供商: {AI_PROVIDER}")
    print(f"  使用模型: {MODEL}")
    print(f"  访问地址: http://localhost:{port}")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=port)
