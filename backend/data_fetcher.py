"""
股票数据获取模块
支持从多个数据源获取实时股票趋势数据
"""
import httpx
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class StockDataFetcher:
    """股票数据获取器"""
    
    def __init__(self):
        self.yahoo_finance_base = "https://query1.finance.yahoo.com/v8/finance/chart"
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    
    async def get_stock_trends(
        self, 
        symbols: List[str],
        periods: List[str] = ["1w", "1mo", "3mo"]
    ) -> Dict[str, Dict]:
        """
        获取股票趋势数据
        
        Args:
            symbols: 股票代码列表，如 ["TSLA", "AAPL"]
            periods: 时间周期列表，如 ["1w", "1mo", "3mo"]
        
        Returns:
            {
                "TSLA": {
                    "symbol": "TSLA",
                    "current_price": 250.5,
                    "trend_1w": {"change": 5.2, "change_percent": 2.1},
                    "trend_1mo": {"change": 12.5, "change_percent": 5.2},
                    "trend_3mo": {"change": 28.3, "change_percent": 12.7},
                    "rsi": 65.2,
                    "volume": 50000000
                }
            }
        """
        results = {}
        
        for symbol in symbols:
            try:
                data = await self._fetch_yahoo_data(symbol, periods)
                if data:
                    results[symbol] = data
            except Exception as e:
                print(f"获取 {symbol} 数据失败: {e}")
                continue
        
        return results
    
    async def _fetch_yahoo_data(
        self, 
        symbol: str, 
        periods: List[str]
    ) -> Optional[Dict]:
        """从Yahoo Finance获取数据"""
        try:
            # 获取当前价格和基本信息
            url = f"{self.yahoo_finance_base}/{symbol}"
            params = {
                "interval": "1d",
                "range": "3mo",
                "includePrePost": "false"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if "chart" not in data or "result" not in data["chart"]:
                    return None
                
                result = data["chart"]["result"][0]
                timestamps = result.get("timestamp", [])
                closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                
                if not closes or not timestamps:
                    return None
                
                current_price = closes[-1] if closes else None
                
                # 计算各周期趋势
                trends = {}
                period_days = {"1w": 7, "1mo": 30, "3mo": 90}
                
                for period in periods:
                    days = period_days.get(period, 30)
                    if len(closes) >= days:
                        old_price = closes[-days] if closes[-days] else closes[0]
                        if old_price and current_price:
                            change = current_price - old_price
                            change_percent = (change / old_price) * 100
                            trends[f"trend_{period}"] = {
                                "change": round(change, 2),
                                "change_percent": round(change_percent, 2),
                                "old_price": round(old_price, 2),
                                "current_price": round(current_price, 2)
                            }
                
                # 计算简单RSI（14日）
                rsi = self._calculate_simple_rsi(closes[-14:]) if len(closes) >= 14 else None
                
                return {
                    "symbol": symbol,
                    "current_price": round(current_price, 2) if current_price else None,
                    **trends,
                    "rsi": round(rsi, 2) if rsi else None,
                    "volume": result.get("indicators", {}).get("quote", [{}])[0].get("volume", [None])[-1]
                }
                
        except Exception as e:
            print(f"Yahoo Finance API错误 ({symbol}): {e}")
            return None
    
    def _calculate_simple_rsi(self, prices: List[float]) -> Optional[float]:
        """计算简单RSI（相对强弱指标）"""
        if len(prices) < 14:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if not gains or not losses:
            return None
        
        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def extract_stock_symbols(self, text: str) -> List[str]:
        """
        从文本中提取股票代码
        
        支持：
        - 美股代码：TSLA, AAPL, MSFT
        - 中文名称映射：特斯拉→TSLA, 苹果→AAPL
        """
        # 美股代码映射（常见股票）
        stock_map = {
            "特斯拉": "TSLA",
            "苹果": "AAPL",
            "微软": "MSFT",
            "英伟达": "NVDA",
            "谷歌": "GOOGL",
            "亚马逊": "AMZN",
            "Meta": "META",
            "脸书": "META",
            "Netflix": "NFLX",
            "奈飞": "NFLX",
            "阿里巴巴": "BABA",
            "腾讯": "TCEHY",
            "比亚迪": "BYDDF",
            "蔚来": "NIO",
            "理想": "LI",
            "小鹏": "XPEV"
        }
        
        import re
        
        # 提取美股代码（大写字母，2-5个字符）
        pattern = r'\b([A-Z]{2,5})\b'
        codes = re.findall(pattern, text.upper())
        
        # 过滤常见单词
        common_words = {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS", "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW", "ITS", "MAY", "NEW", "NOW", "OLD", "SEE", "TWO", "WAY", "WHO", "BOY", "DID", "ITS", "LET", "PUT", "SAY", "SHE", "TOO", "USE"}
        codes = [c for c in codes if c not in common_words and len(c) >= 2]
        
        # 提取中文名称并映射
        for chinese_name, symbol in stock_map.items():
            if chinese_name in text:
                if symbol not in codes:
                    codes.append(symbol)
        
        # 去重并返回
        return list(set(codes))


# 全局实例
stock_fetcher = StockDataFetcher()

