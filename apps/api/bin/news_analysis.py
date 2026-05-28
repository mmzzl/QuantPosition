# -*- coding: utf-8 -*-
"""
财经新闻分析脚本
读取当天新闻 → LLM分类摘要 → LLM市场分析 → 推送钉钉
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import random
import logging
from datetime import datetime
from systems.logs import Log
from systems.single import ScriptSingle
from systems.sys import home
from database import get_db


# ============================================================
# LLM 调用（复用 rule_explorer 的模式）
# ============================================================

def call_llm(system_prompt: str, user_msg: str, settings: dict, temperature=0.7, max_tokens=4000) -> str:
    """调用 LLM，返回文本内容"""
    from openai import OpenAI, RateLimitError, APIError

    api_url = settings.get("llm_api_url", "").rstrip("/")
    api_key = settings.get("llm_api_key", "")
    model = settings.get("llm_model", "gpt-4o-mini")

    if not api_url or not api_key:
        raise ValueError("LLM 未配置，请在系统设置中配置 API Key")

    client = OpenAI(base_url=api_url, api_key=api_key)

    for attempt in range(6):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
            return completion.choices[0].message.content.strip()

        except RateLimitError:
            wait = (2 ** attempt) + random.uniform(0.5, 1.5)
            logging.warning(f"[NEWS_ANALYSIS] 429 限流，等 {wait:.1f}s 后重试 ({attempt+1}/6)")
            time.sleep(wait)

        except APIError as e:
            wait = (2 ** attempt) + random.uniform(0.5, 1.5)
            logging.warning(f"[NEWS_ANALYSIS] API错误: {e}，等 {wait:.1f}s 后重试")
            time.sleep(wait)

        except Exception as e:
            logging.error(f"[NEWS_ANALYSIS] LLM调用失败: {e}")
            if attempt == 5:
                raise
            time.sleep(2)

    raise RuntimeError("LLM 调用重试 6 次仍然失败")


# ============================================================
# 第一步：新闻分类 + 摘要
# ============================================================

CLASSIFY_PROMPT = """你是一位专业的财经新闻编辑。请将以下新闻按类别分类，并为每条新闻生成简短摘要。

分类规则：
- 【科技前沿】：AI、芯片、云计算、新能源技术、科技公司动态
- 【财报业绩】：上市公司财报、业绩预告、利润数据
- 【市场动态】：大盘走势、资金流向、政策变化、行业趋势
- 【风险警示】：ST风险、退市警告、立案调查、业绩变脸
- 如果某个类别没有相关新闻，不要输出该类别

输出格式要求：
- 每个类别用【类别名】作为标题
- 每条新闻一行，格式：序号. 标题（一句话概括核心信息）
- 每个类别最多选 5 条最重要的新闻
- 不要输出其他文字，只输出分类结果"""


def classify_news(news_list: list, settings: dict) -> str:
    """第一步：LLM 分类新闻"""
    # 构建新闻文本，限制长度
    news_text = "\n".join([
        f"[{i+1}] {n['title']}：{n.get('summary', '')[:200]}"
        for i, n in enumerate(news_list)
    ])

    user_msg = f"以下是今天的 {len(news_list)} 条财经新闻，请分类整理：\n\n{news_text}"
    logging.info(f"[NEWS_ANALYSIS] 第一步：分类 {len(news_list)} 条新闻...")
    return call_llm(CLASSIFY_PROMPT, user_msg, settings, temperature=0.5, max_tokens=3000)


# ============================================================
# 第二步：市场分析
# ============================================================

ANALYSIS_PROMPT = """你是一位资深财经分析师。请基于今日新闻分类结果，生成简洁的市场分析报告。

输出格式要求（严格按此结构）：

🤖 今日市场分析

1. 市场整体态势
（2-3句话概括今日市场主线）

2. 板块轮动
（列出3-4个热点板块，每个一行，用 - 开头）

3. 投资机会
✅ 机会：
（列出2-3个机会方向）
⚠️ 风险：
（列出2-3个风险点）

4. 明日展望
（2-3句话，列出需要关注的事项）

💡 今日核心关注：
（列出3-4个最值得关注的要点，每行一个，用 - 开头）

要求：
- 语言简洁有力，适合手机阅读
- 不要重复新闻原文，只做分析和总结
- 总字数控制在 500 字以内"""


def generate_analysis(classified_text: str, settings: dict) -> str:
    """第二步：LLM 生成市场分析"""
    user_msg = f"以下是今日新闻分类结果，请生成市场分析：\n\n{classified_text}"
    logging.info("[NEWS_ANALYSIS] 第二步：生成市场分析...")
    return call_llm(ANALYSIS_PROMPT, user_msg, settings, temperature=0.6, max_tokens=2000)


# ============================================================
# 主流程
# ============================================================

def fetch_today_news() -> list:
    """从 MongoDB 获取当天新闻"""
    db = get_db()
    today_str = datetime.now().strftime("%Y-%m-%d")
    # showTime 格式为 "2026-05-28 15:30:00"
    news_list = list(db.news.find(
        {"showTime": {"$gte": f"{today_str} 00:00:00", "$lte": f"{today_str} 23:59:59"}}
    ).sort("showTime", 1))

    logging.info(f"[NEWS_ANALYSIS] 获取到 {len(news_list)} 条今日新闻")
    return news_list


def run_news_analysis():
    """主函数：分析新闻并推送钉钉"""
    from bin.rule_engine import send_dingtalk_message

    db = get_db()
    settings = db.system_settings.find_one({"_id": "global"}) or {}

    # 1. 获取新闻
    news_list = fetch_today_news()
    if not news_list:
        logging.warning("[NEWS_ANALYSIS] 今天没有新闻，跳过")
        return

    # 2. 去重（按标题去重）
    seen = set()
    unique_news = []
    for n in news_list:
        title = n.get("title", "").strip()
        if title and title not in seen:
            seen.add(title)
            unique_news.append(n)
    logging.info(f"[NEWS_ANALYSIS] 去重后 {len(unique_news)} 条")

    # 3. 第一次 LLM：分类摘要
    classified = classify_news(unique_news, settings)

    # 4. 第二次 LLM：市场分析
    analysis = generate_analysis(classified, settings)

    # 5. 拼接完整内容
    today_str = datetime.now().strftime("%Y-%m-%d")
    full_content = f"{classified}\n\n---\n\n{analysis}"

    # 6. 推送钉钉
    title = f"📰 财经日报 {today_str}"
    logging.info(f"[NEWS_ANALYSIS] 推送钉钉: {title}")
    success = send_dingtalk_message(title, full_content)
    if success:
        logging.info("[NEWS_ANALYSIS] 推送成功")
    else:
        logging.error("[NEWS_ANALYSIS] 推送失败")

    return {"success": success, "news_count": len(unique_news), "content": full_content}


if __name__ == "__main__":
    Log("news_analysis", log_type=Log.TYPE_FILE, level=logging.INFO)
    pid_file = os.path.join(home(), 'apps', 'api', 'var', 'run', 'news_analysis.pid')
    single = ScriptSingle(pid_file)

    if single.is_running():
        logging.error('there is script lock {}'.format(pid_file))
        sys.exit(0)

    run_news_analysis()
