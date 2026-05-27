"""
强力爬虫模块 - 多引擎搜索 + 网页内容抓取
支持：Bing、百度、搜狗、DuckDuckGo 多引擎并发搜索
      真实浏览器指纹、代理池、智能重试、HTML清洗
"""
import httpx
import re
import time
import random
import asyncio
from urllib.parse import quote, urlparse
from bs4 import BeautifulSoup


# ==================== 配置 ====================
CRAWLER_CONFIG = {
    "max_concurrent_fetches": 5,      # 并发抓取网页数
    "page_timeout": 15,               # 单页超时（秒）
    "total_timeout": 25,              # 总抓取超时（秒）
    "max_retries": 2,                 # 最大重试次数
    "retry_base_delay": 1.0,          # 重试基础延迟（秒）
    "max_content_per_page": 5000,     # 每个网页最大提取字符数
    "max_context_length": 12000,      # 搜索上下文最大总长度
    "search_max_results": 8,          # 搜索结果数
    "search_timeout": 12,             # 搜索超时（秒）
}

# ==================== UA 池 ====================
UA_POOL = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

ACCEPT_LANGUAGE_POOL = [
    "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "zh-CN,zh-Hans;q=0.9,en;q=0.8,ja;q=0.7",
]

# ==================== 搜索引擎配置 ====================
SEARCH_ENGINES = [
    {
        "name": "Bing",
        "url": "https://www.bing.com/search?q={query}&count={count}&setlang=zh-cn&mkt=zh-CN",
        "parser": "parse_bing",
        "priority": 1,
    },
    {
        "name": "Bing_CN",
        "url": "https://cn.bing.com/search?q={query}&count={count}&setlang=zh-cn&mkt=zh-CN",
        "parser": "parse_bing",
        "priority": 2,
    },
    {
        "name": "Baidu",
        "url": "https://www.baidu.com/s?wd={query}&ie=utf-8&rn=15",
        "parser": "parse_baidu",
        "priority": 3,
    },
    {
        "name": "Sogou",
        "url": "https://www.sogou.com/web?query={query}&ie=utf8",
        "parser": "parse_sogou",
        "priority": 4,
    },
    {
        "name": "DuckDuckGo",
        "url": "https://lite.duckduckgo.com/lite/?q={query}",
        "parser": "parse_duckduckgo",
        "priority": 5,
    },
]


def get_random_ua():
    return random.choice(UA_POOL)


def build_headers(referer="https://www.google.com/"):
    return {
        "User-Agent": get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": random.choice(ACCEPT_LANGUAGE_POOL),
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
    }


# ==================== 搜索结果解析器 ====================

def parse_bing(html, max_results):
    """解析 Bing 搜索结果"""
    results = []
    soup = BeautifulSoup(html, "html.parser")

    # 策略1: 标准 b_algo 结构
    for item in soup.select("li.b_algo"):
        if len(results) >= max_results:
            break
        link = item.select_one("h2 a")
        if not link:
            continue
        url = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or not url or "bing.com" in url or "go.microsoft.com" in url:
            continue

        snippet_el = item.select_one("p.b_lineclamp2, p.b_lineclamp3, .b_caption p")
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""

        results.append({
            "title": title[:100],
            "url": url,
            "snippet": snippet[:500],
            "source": "Bing",
        })

    # 策略2: 宽松匹配
    if not results:
        for link in soup.select("h2 a[href]"):
            if len(results) >= max_results:
                break
            url = link.get("href", "")
            title = link.get_text(strip=True)
            if title and url and url.startswith("http") and "bing.com" not in url:
                results.append({
                    "title": title[:100],
                    "url": url,
                    "snippet": "",
                    "source": "Bing",
                })

    return results


def parse_baidu(html, max_results):
    """解析百度搜索结果"""
    results = []
    soup = BeautifulSoup(html, "html.parser")

    for item in soup.select(".result, .c-container"):
        if len(results) >= max_results:
            break
        # 跳过广告
        if "ec_ad" in str(item) or "result-op" in str(item):
            continue

        link = item.select_one("h3 a")
        if not link:
            continue
        url = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or not url or "baidu.com" in url:
            continue

        snippet_el = item.select_one(".c-abstract, .c-span-last, .content-right_8Zs40")
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""

        results.append({
            "title": title[:100],
            "url": url,
            "snippet": snippet[:500],
            "source": "百度",
        })

    return results


def parse_sogou(html, max_results):
    """解析搜狗搜索结果"""
    results = []
    soup = BeautifulSoup(html, "html.parser")

    for item in soup.select(".rb, .vrwrap, .result"):
        if len(results) >= max_results:
            break
        link = item.select_one("h3 a")
        if not link:
            continue
        url = link.get("href", "")
        title = link.get_text(strip=True)

        # 搜狗重定向链接
        if "sogou.com/link" in url:
            m = re.search(r"url=([^&]+)", url)
            if m:
                from urllib.parse import unquote
                url = unquote(m.group(1))

        if not title or not url or not url.startswith("http") or "sogou.com" in url:
            continue

        snippet_el = item.select_one(".str_info, .abstract, .summary, .space-txt, p")
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""

        results.append({
            "title": title[:100],
            "url": url,
            "snippet": snippet[:500],
            "source": "搜狗",
        })

    return results


def parse_duckduckgo(html, max_results):
    """解析 DuckDuckGo Lite 搜索结果"""
    results = []
    soup = BeautifulSoup(html, "html.parser")

    links = []
    for a in soup.select("a[href]"):
        url = a.get("href", "")
        title = a.get_text(strip=True)
        if url and title and "duckduckgo.com" not in url and not title.startswith("<"):
            links.append({"url": url, "title": title})

    snippets = []
    for span in soup.select(".snippet, .result-snippet"):
        snippets.append(span.get_text(strip=True))

    for i in range(min(len(links), max_results)):
        results.append({
            "title": links[i]["title"][:100],
            "url": links[i]["url"],
            "snippet": snippets[i][:500] if i < len(snippets) else "",
            "source": "DuckDuckGo",
        })

    return results


# ==================== 搜索引擎调度 ====================

async def search_with_engine(client, engine, query, max_results):
    """用单个搜索引擎搜索"""
    url = engine["url"].format(query=quote(query), count=max_results)
    headers = build_headers()

    try:
        resp = await client.get(
            url,
            headers=headers,
            follow_redirects=True,
            timeout=CRAWLER_CONFIG["search_timeout"],
        )
        if resp.status_code != 200:
            print(f"  [{engine['name']}] HTTP {resp.status_code}")
            return []

        html = resp.text
        parser_func = globals().get(engine["parser"])
        if parser_func:
            results = parser_func(html, max_results)
            print(f"  [{engine['name']}] 找到 {len(results)} 个结果")
            return results
    except Exception as e:
        print(f"  [{engine['name']}] 搜索出错: {e}")

    return []


async def multi_engine_search(query, max_results=None):
    """多引擎并发搜索"""
    if max_results is None:
        max_results = CRAWLER_CONFIG["search_max_results"]

    # 按优先级排序
    engines = sorted(SEARCH_ENGINES, key=lambda e: e["priority"])

    async with httpx.AsyncClient(
        timeout=CRAWLER_CONFIG["search_timeout"],
        limits=httpx.Limits(max_connections=10),
    ) as client:
        tasks = [search_with_engine(client, eng, query, max_results) for eng in engines]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

    # 合并结果
    merged = []
    for results in all_results:
        if isinstance(results, list):
            merged.extend(results)

    # 去重
    seen = set()
    unique = []
    for r in merged:
        url = normalize_url(r.get("url", ""))
        if url and url not in seen and r.get("url", "").startswith("http"):
            seen.add(url)
            unique.append(r)

    # 质量排序
    unique.sort(key=lambda r: (len(r.get("snippet", "")) > 20, "百度" in r.get("source", "") or "Bing" in r.get("source", "")), reverse=True)

    return unique[:max_results]


# ==================== 网页内容抓取 ====================

async def fetch_page_content(client, url):
    """抓取单个网页内容"""
    headers = build_headers()

    try:
        resp = await client.get(
            url,
            headers=headers,
            follow_redirects=True,
            timeout=CRAWLER_CONFIG["page_timeout"],
        )

        if resp.status_code in (403, 429):
            print(f"  反爬拦截: {url} ({resp.status_code})")
            return None

        if resp.status_code != 200:
            print(f"  HTTP错误: {url} ({resp.status_code})")
            return None

        # 检查是否被重定向到验证页面
        final_url = str(resp.url)
        if any(kw in final_url for kw in ("captcha", "challenge", "verify")):
            print(f"  遇到验证页面: {url}")
            return None

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return None

        html = resp.text

        # 检测拦截页面
        if is_block_page(html):
            print(f"  检测到拦截页面: {url}")
            return None

        return clean_html(html)

    except Exception as e:
        print(f"  抓取失败 {url}: {e}")
        return None


async def fetch_page_with_retry(client, url, max_retries=None):
    """带重试的网页抓取"""
    if max_retries is None:
        max_retries = CRAWLER_CONFIG["max_retries"]

    for attempt in range(max_retries + 1):
        result = await fetch_page_content(client, url)
        if result is not None:
            return result
        if attempt < max_retries:
            delay = CRAWLER_CONFIG["retry_base_delay"] * (2 ** attempt) + random.uniform(0, 0.5)
            print(f"  重试 {url} (第{attempt + 1}次)，等待 {delay:.1f}s")
            await asyncio.sleep(delay)
    return None


async def enrich_with_crawler(search_results, query):
    """爬虫抓取搜索结果中的网页内容"""
    urls_to_fetch = [
        r for r in search_results
        if r.get("url", "").startswith("http")
    ][:CRAWLER_CONFIG["max_concurrent_fetches"]]

    if not urls_to_fetch:
        return search_results

    print(f"爬虫开始抓取 {len(urls_to_fetch)} 个网页...")

    async with httpx.AsyncClient(
        timeout=CRAWLER_CONFIG["page_timeout"],
        limits=httpx.Limits(max_connections=CRAWLER_CONFIG["max_concurrent_fetches"]),
    ) as client:
        tasks = []
        for result in urls_to_fetch:
            tasks.append(fetch_and_extract(client, result, query))

        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=CRAWLER_CONFIG["total_timeout"],
            )
        except asyncio.TimeoutError:
            print("爬虫总超时")

    crawled = sum(1 for r in search_results if r.get("hasCrawled"))
    print(f"爬虫完成: {crawled}/{len(urls_to_fetch)} 个网页成功抓取")

    return search_results


async def fetch_and_extract(client, result, query):
    """抓取并提取相关内容"""
    url = result.get("url", "")
    try:
        print(f"  爬虫抓取: {url}")
        content = await fetch_page_with_retry(client, url)
        if content:
            relevant = extract_relevant_content(content, query, CRAWLER_CONFIG["max_content_per_page"])
            if relevant:
                result["fullContent"] = relevant
                result["hasCrawled"] = True
                print(f"  爬虫成功: {url} ({len(relevant)} 字符)")
            else:
                print(f"  爬虫跳过: {url} (无相关内容)")
        else:
            print(f"  爬虫跳过: {url} (无内容或被拦截)")
    except Exception as e:
        print(f"  爬虫失败 {url}: {e}")
    return result


# ==================== HTML 清洗 ====================

def clean_html(html):
    """从 HTML 中提取纯文本正文"""
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # 移除不需要的标签
    for tag in soup(["script", "style", "noscript", "iframe", "svg",
                      "nav", "footer", "header", "aside", "form",
                      "select", "button", "textarea", "canvas",
                      "video", "audio", "source", "track"]):
        tag.decompose()

    # 获取文本
    text = soup.get_text(separator="\n", strip=True)

    # 清理空白
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)

    # 合并短行
    merged = []
    for line in lines:
        if merged and len(line) < 40 and len(merged[-1]) < 200:
            merged[-1] += " " + line
        else:
            merged.append(line)

    return "\n\n".join(merged)


def is_block_page(html):
    """检测是否被反爬拦截"""
    if not html or len(html) < 100:
        return False

    signatures = [
        "cf-browser-verification", "cf-challenge-running",
        "cf_captcha", "g-recaptcha", "h-captcha",
        "Just a moment", "Checking your browser",
        "Please enable JavaScript", "请启用 JavaScript",
        "请开启 JavaScript", "DDoS protection",
        "Attention Required", "Cloudflare Ray ID",
        "_cf_chl_opt", "challenge-platform",
    ]

    lower = html[:3000].lower()
    return any(sig.lower() in lower for sig in signatures)


# ==================== 内容提取 ====================

def extract_relevant_content(text, query, max_length=5000):
    """从网页内容中提取与查询相关的段落"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text

    keywords = extract_keywords(query)
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]

    if not paragraphs:
        return text[:max_length]

    # 计算相关性得分
    scored = []
    for p in paragraphs:
        lower_p = p.lower()
        score = 0
        for kw in keywords:
            score += lower_p.count(kw.lower()) * 10
        # 段落长度适中加分
        if 100 < len(p) < 800:
            score += 5
        # 包含数字/日期加分
        if re.search(r"\d{4}年|\d{2}月|\d{2}日|\d{2}:\d{2}", p):
            score += 3
        scored.append((p, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    result = ""
    for text, _ in scored:
        if len(result) + len(text) > max_length:
            remaining = max_length - len(result)
            if remaining > 100:
                result += text[:remaining] + "..."
            break
        result += text + "\n\n"

    return result.strip() or text[:max_length]


def extract_keywords(query):
    """从查询中提取关键词"""
    stop_words = {
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
        "没有", "看", "好", "自己", "这", "那", "他", "她", "它", "们",
        "什么", "怎么", "哪", "吗", "吧", "呢", "啊", "哦", "嗯",
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "can", "shall",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "and", "or", "but", "not", "so", "if", "as", "it", "its",
        "this", "that", "these", "those", "we", "you", "they",
    }

    cleaned = re.sub(r"[，。！？、；：\u201c\u201d\u2018\u2019（）【】《》\s,.!?;:'\"()\[\]{}<>/\\|@#$%^&*+=~`-]", " ", query)
    words = [w for w in cleaned.split() if len(w) >= 2 and w.lower() not in stop_words]

    if len(words) < 2:
        return [query]

    return list(set(words))


# ==================== 工具函数 ====================

def normalize_url(url):
    """标准化 URL 用于去重"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/").lower()
    except Exception:
        return url.lower()


def get_current_date():
    """获取当前北京时间"""
    from datetime import datetime, timezone, timedelta
    bj_tz = timezone(timedelta(hours=8))
    now = datetime.now(bj_tz)
    return now.strftime("%Y年%m月%d日 %H:%M（北京时间）")


# ==================== 主入口 ====================

async def web_search(query, max_results=None):
    """
    联网搜索 + 爬虫抓取
    返回: (results_list, search_context_string)
    """
    if max_results is None:
        max_results = CRAWLER_CONFIG["search_max_results"]

    print(f"\n{'='*50}")
    print(f"搜索查询: {query}")
    print(f"{'='*50}")

    # 1. 多引擎搜索
    results = await multi_engine_search(query, max_results)
    print(f"搜索完成: 共 {len(results)} 个去重结果")

    if not results:
        return [], ""

    # 2. 爬虫抓取网页内容
    results = await enrich_with_crawler(results, query)

    # 3. 构建搜索上下文
    context = build_search_context(results, query)

    return results, context


def build_search_context(results, query):
    """构建搜索上下文文本"""
    if not results:
        return ""

    context = f"当前日期：{get_current_date()}\n\n"
    context += f"以下是用户问题「{query}」的网络搜索结果，你必须参考这些信息来回答：\n\n"
    context += "=== 搜索结果 ===\n"

    for i, r in enumerate(results, 1):
        context += f"[{i}] {r.get('title', '')}\n"
        if r.get("url"):
            context += f"来源: {r['url']}\n"

        if r.get("hasCrawled") and r.get("fullContent"):
            context += f"网页内容（爬虫抓取）:\n{r['fullContent']}\n"
        elif r.get("snippet"):
            context += f"摘要: {r['snippet']}\n"
        context += "\n"

    context += "=== 搜索结束 ===\n"
    context += '重要：你必须基于以上搜索结果回答用户问题。如果搜索结果中包含\u201c网页内容（爬虫抓取）\u201d，请优先参考这些真实网页内容。在回答中引用搜索到的信息，并注明来源。如果搜索结果与问题不相关，请说明并基于你的知识回答。'

    if len(context) > CRAWLER_CONFIG["max_context_length"]:
        context = context[:CRAWLER_CONFIG["max_context_length"] - 50] + "\n...(搜索结果已截断)\n=== 搜索结束 ==="

    return context


# ==================== 同步包装器（供 Flask 调用）====================

def sync_web_search(query, max_results=None):
    """同步版本的 web_search，供 Flask 路由调用"""
    return asyncio.run(web_search(query, max_results))
