"""
AI问答系统 - 配置文件
在这里配置您的AI API密钥以启用高级AI功能
支持：OpenAI、硅基流动(SiliconFlow)、DeepSeek等
"""

# ========== AI API配置 ==========

# 选择AI服务提供商：
# 1. OpenAI: https://platform.openai.com/api-keys
# 2. 硅基流动 SiliconFlow: https://cloud.siliconflow.cn/account/ak
# 3. DeepSeek: https://platform.deepseek.com
# 4. 其他兼容OpenAI格式的服务

# 【推荐】使用硅基流动（性价比高，国内访问快）
# 注册获取API密钥: https://cloud.siliconflow.cn/account/ak
AI_PROVIDER = "siliconflow"  # 可选: openai, siliconflow, deepseek

# 硅基流动配置
SILICONFLOW_API_KEY = "sk-uwqilscdtxfnjsaqsaxjfeoqbsecyyixnpgipugnfuabsfgv"  # 在此填入您的硅基流动API密钥
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"  # 或其他可用模型

# OpenAI配置（备选）
OPENAI_API_KEY = ""
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-3.5-turbo"

# DeepSeek配置（备选）
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

# ========== 根据提供商自动配置 ==========

if AI_PROVIDER == "siliconflow":
    API_KEY = SILICONFLOW_API_KEY
    BASE_URL = SILICONFLOW_BASE_URL
    MODEL = SILICONFLOW_MODEL
elif AI_PROVIDER == "deepseek":
    API_KEY = DEEPSEEK_API_KEY
    BASE_URL = DEEPSEEK_BASE_URL
    MODEL = DEEPSEEK_MODEL
else:  # openai
    API_KEY = OPENAI_API_KEY
    BASE_URL = OPENAI_BASE_URL
    MODEL = OPENAI_MODEL

# ========== 其他配置 ==========

# 搜索参数 - 大量爬取策略
MAX_SEARCH_RESULTS = 30  # 搜索30个结果（百度可能返回较少）
MAX_PAGES_TO_CRAWL = 20  # 爬取20个网页
CRAWL_DELAY = 0.4        # 适当增加延迟，提高成功率
MAX_CONTENT_LENGTH = 5000  # 单个页面最大内容长度
