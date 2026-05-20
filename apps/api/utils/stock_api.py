import requests
from typing import Optional, Dict
import re
import logging

logger = logging.getLogger(__name__)


class SinaStockAPI:
    """新浪股票行情 API"""

    BASE_URL = "http://hq.sinajs.cn/list="

    @staticmethod
    def _get_stock_code(code: str) -> str:
        """转换股票代码为新浪格式"""
        code = code.strip()
        if len(code) == 6:
            if code.startswith(('6', '5')):
                return f"sh{code}"
            elif code.startswith(('0', '3')):
                return f"sz{code}"
        return code

    @staticmethod
    def get_price(code: str) -> Optional[float]:
        """
        获取股票当前价格
        """
        try:
            sina_code = SinaStockAPI._get_stock_code(code)
            url = f"{SinaStockAPI.BASE_URL}{sina_code}"

            headers = {"Referer": "https://finance.sina.com.cn"}
            response = requests.get(url, headers=headers, timeout=5)
            response.encoding = 'gbk'

            if response.status_code == 200:
                content = response.text
                match = re.search(r'="([^"]+)"', content)
                if match:
                    data = match.group(1).split(',')
                    if len(data) > 3 and data[3]:
                        return float(data[3])
            return None
        except Exception as e:
            logger.error(f"Error fetching price for {code}: {e}")
            return None

    @staticmethod
    def get_stock_info(code: str) -> Optional[Dict]:
        """
        获取股票详细信息
        """
        try:
            sina_code = SinaStockAPI._get_stock_code(code)
            url = f"{SinaStockAPI.BASE_URL}{sina_code}"

            headers = {
                "Referer": "https://finance.sina.com.cn"
            }
            response = requests.get(url, headers=headers, timeout=5)
            response.encoding = 'gbk'

            logger.info(f"[SinaAPI] Request: {url}, Status: {response.status_code}")
            logger.info(f"[SinaAPI] Response content: {response.text[:200]}")

            if response.status_code == 200:
                content = response.text
                match = re.search(r'="([^"]+)"', content)
                if match:
                    data = match.group(1).split(',')
                    if len(data) > 9:
                        return {
                            "name": data[0],
                            "price": float(data[3]) if data[3] else None,
                            "open": float(data[1]) if data[1] else None,
                            "high": float(data[4]) if data[4] else None,
                            "low": float(data[5]) if data[5] else None,
                            "volume": int(data[8]) if data[8] else None,
                            "amount": float(data[9]) if data[9] else None,
                        }
                else:
                    logger.warning(f"[SinaAPI] No match found in response for {code}")
            return None
        except Exception as e:
            logger.error(f"[SinaAPI] Error fetching info for {code}: {e}")
            return None


def get_stock_price(code: str) -> Optional[float]:
    """便捷函数：获取股票价格"""
    return SinaStockAPI.get_price(code)


def get_stock_name(code: str) -> Optional[str]:
    """便捷函数：获取股票名称"""
    info = SinaStockAPI.get_stock_info(code)
    return info.get("name") if info else None