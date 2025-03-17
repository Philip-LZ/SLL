"""搜索模块，提供Bocha搜索功能"""

import os
import json
import logging
import requests
from typing import List, Dict

class BochaSearch:
    """Bocha搜索引擎接口"""
    def __init__(self, search_top_k: int):
        self.search_top_k = search_top_k
        self.logger = logging.getLogger(__name__)

    def search(self, query: str) -> List[Dict[str, str]]:
        """执行Bocha搜索并返回结果"""
        try:
            url = "https://api.bochaai.com/v1/web-search"
            payload = json.dumps({
                "query": query,
                "summary": True,
                "count": self.search_top_k,
                "page": 1
            })
            headers = {
                'Authorization': f'Bearer {os.getenv("BOSHA_API_KEY")}',
                'Content-Type': 'application/json'
            }
            response = requests.post(url, headers=headers, data=payload)
            res = response.json()

            results = []
            if res.get('code') == 200 and 'data' in res:
                web_pages = res['data'].get('webPages', {})
                if 'value' in web_pages:
                    for item in web_pages['value']:
                        results.append({
                            'title': item.get('name', ''),
                            'link': item.get('url', ''),
                            'snippet': item.get('summary', '')
                        })
            return results
        except Exception as e:
            self.logger.error(f"Bocha search error: {str(e)}")
            return []