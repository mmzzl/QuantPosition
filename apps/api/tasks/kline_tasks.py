import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from celery_config import celery_app
from bin.kline_spider import StockKlineScraper


@celery_app.task(bind=True, name="tasks.kline.update")
def update_kline_data(self):
    """更新 K 线数据"""
    self.update_state(state='PROGRESS', meta={'status': '开始更新 K 线数据...'})
    scraper = StockKlineScraper()
    result = scraper.fetch_daily_klines()
    msg = f"K 线更新完成: 成功={result['success']}, 跳过={result['skipped']}, 失败={result['failed']}"
    self.update_state(state='PROGRESS', meta={'status': msg})
    return result
