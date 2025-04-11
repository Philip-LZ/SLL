import concurrent.futures
import json
import logging
import os
from typing import List, Dict, Union

import httpx
import requests
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ratelimit import sleep_and_retry, limits
from sqlalchemy.sql import text

load_dotenv()

# 设置速率限制，每秒最多1个请求
CALLS = 1
RATE_LIMIT_PERIOD = 1  # 秒


class BochaSearch:
    """Bocha搜索引擎接口"""

    def __init__(self,
                 database_engine,
                 bocha_search_api=None,
                 k: int = 1,
                 min_char_count: int = 150,
                 snippet_chunk_size: int = 1000,
                 max_threads: int = 3,
                 ):
        """初始化Bocha搜索类
        Args:
            bocha_search_api: Bocha API密钥，如果未提供则从环境变量BOCHA_API_KEY获取
            k: 每次搜索返回的结果数量
            min_char_count: 最小字符数
            snippet_chunk_size: 片段大小
            max_threads: 最大线程数
        """
        self.k = k
        self.usage = 0
        self.max_threads = max_threads
        self.min_char_count = min_char_count
        self.httpx_client = httpx.Client(verify=False)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=snippet_chunk_size,
            chunk_overlap=100,
            length_function=len,
            is_separator_regex=False,
            separators=[
                "\n\n",
                "\n",
                "。",
                "，",
                "\u200B",  # Zero-width space
                "",
            ],
        )
        self.bocha_api_key = bocha_search_api or os.getenv("BOCHA_API_KEY")
        if not self.bocha_api_key:
            raise RuntimeError("必须提供bocha_search_api参数或设置BOCHA_API_KEY环境变量")
        self.database_engine = database_engine

    def get_usage_and_reset(self) -> Dict[str, int]:
        """获取并重置使用计数
        Returns:
            包含使用计数的字典
        """
        usage = self.usage
        self.usage = 0
        return {"BochaSearch": usage}

    @sleep_and_retry
    @limits(calls=CALLS, period=RATE_LIMIT_PERIOD)
    def _process_single_query(self, query: str) -> List[Dict[str, Union[str, List[str]]]]:
        """处理单个查询
        Args:
            query: 查询字符串
        Returns:
            查询结果列表
        """
        results = []
        url = "https://api.bochaai.com/v1/web-search"
        headers = {
            'Authorization': f'Bearer {os.getenv("BOCHA_API_KEY")}',
            'Content-Type': 'application/json'
        }

        try:
            payload = json.dumps({
                "query": query,
                "summary": True,
                "count": self.k,
                "page": 1
            })

            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            res = response.json()

            if res.get('code') != 200:
                logging.warning(f"Bocha API返回非200状态码: {res.get('code')}，查询: {query}")
                return results

            web_pages = res.get('data', {}).get('webPages', {})
            if not web_pages.get('value'):
                logging.info(f"查询 '{query}' 未返回任何结果")
                return results

            for item in web_pages['value']:
                url = item.get('url', '')
                summary = item.get('summary', '')
                results.append({
                    'description': summary,
                    'snippets': [summary] if summary else [],
                    'title': item.get('name', ''),
                    'url': url
                })

        except requests.exceptions.RequestException as e:
            logging.error(f"Bocha API请求失败，查询: {query}, 错误: {str(e)}")
        except json.JSONDecodeError as e:
            logging.error(f"Bocha API返回的JSON解析失败，查询: {query}, 错误: {str(e)}")
        except Exception as e:
            logging.error(f"搜索查询 '{query}' 时发生未知错误: {str(e)}")

        return results

    def search(self, query_or_queries: Union[str, List[str]]) -> List[Dict[str, Union[str, List[str]]]]:
        """使用Bocha搜索引擎执行查询，支持多线程处理查询列表
        Args:
            query_or_queries: 要搜索的查询字符串或查询列表
        Returns:
            包含搜索结果的字典列表，每个字典包含'description'、'snippets'、'title'和'url'字段
        """
        # 将查询字符串转换为查询列表
        queries = [query_or_queries] if isinstance(query_or_queries, str) else query_or_queries
        # 增加查询次数
        self.usage += len(queries)
        # 初始化结果列表
        collected_results = []

        # 使用线程池并行处理查询
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            # 提交所有查询任务
            future_to_query = {executor.submit(self._process_single_query, query): query for query in queries}

            # 收集所有查询结果
            for future in concurrent.futures.as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    # 获取查询结果
                    results = future.result()
                    # 将查询结果添加到结果列表中
                    collected_results.extend(results)
                except Exception as e:
                    # 记录错误日志
                    logging.error(f"处理查询 '{query}' 时发生错误: {str(e)}")

        # 如果有查询结果，则保存到数据库
        if collected_results:
            self.save_to_database(collected_results)

        # 返回查询结果
        return collected_results

    def save_to_database(self, search_results: List[Dict[str, str]]):
        """将搜索结果保存到数据库"""
        try:
            # 直接使用 engine 对象创建连接
            with self.database_engine.connect() as conn:
                for result in search_results:
                    description = result.get('description', '')
                    if description:
                        split_descriptions = self.text_splitter.split_text(description)
                        split_descriptions = [chunk for chunk in split_descriptions if
                                              len(chunk) >= self.min_char_count]
                        result['description'] = "\n".join(split_descriptions)

                    # Delete existing record if lnk exists
                    delete_query = text("""
                        DELETE FROM research WHERE lnk = :lnk
                    """)
                    conn.execute(delete_query, {'lnk': result.get('url', '')})

                    # Insert the new record
                    insert_query = text("""
                        INSERT INTO research (title, lnk, snippet)
                        VALUES (:title, :lnk, :snippet)
                    """)

                    conn.execute(insert_query, {
                        'title': result.get('title', ''),
                        'lnk': result.get('url', ''),
                        'snippet': result.get('description', ''),
                    })
                conn.commit()

        except Exception as e:
            logging.error(f"保存搜索结果到数据库时发生错误: {str(e)}")
            raise


if __name__ == '__main__':
    from backend.SLL_longtext.engine import SLLDatabaseEngine

    db_engine = SLLDatabaseEngine()
    search = BochaSearch(
        bocha_search_api="sk-999323aed0d446748ff32d4c242cd1b9", 
        database_engine=db_engine.engine
    )
    search.search("python")
