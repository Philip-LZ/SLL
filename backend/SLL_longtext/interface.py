import concurrent.futures
import dspy
import functools
import hashlib
import json
import logging
import time
from collections import OrderedDict
from abc import ABC, abstractmethod

logging.basicConfig(
    level=logging.INFO, format="%(name)s : %(levelname)-8s : %(message)s"
)
logger = logging.getLogger(__name__)


class InformationTable(ABC):
    """
    InformationTable类用作数据类，用于存储在KnowledgeCuration阶段收集的信息。

    根据需要创建子类以包含 以视角为导向 的对话历史
    """

    def __init__(self):
        pass

    @abstractmethod
    def retrieve_information(**kwargs):
        pass


class Information:
    """详细信息。

    从信息继承以包含唯一标识符（URL），并使用风暴信息的描述、片段和标题对其进行扩展。

    属性：
    摘录（列表）：简短摘录或摘录的列表。
    title（str）：信息的标题或标题。
    url（str）：信息的唯一url（用作UUID）。

    """

    def __init__(self, url, snippets, title, meta=None):
        """Initialize the Information object with detailed attributes.

        Args:
            url (str): The unique URL serving as the identifier for the information.
            snippets (list): List of brief excerpts or snippet.
            title (str): The title or headline of the information.
        """
        self.snippets = snippets
        self.title = title
        self.url = url
        self.meta = meta if meta is not None else {}
        self.citation_uuid = -1

    def __hash__(self):
        return hash(
            (
                self.url,
                tuple(sorted(self.snippets)),
            )
        )

    def __eq__(self, other):
        if not isinstance(other, Information):
            return False
        return (
                self.url == other.url
                and set(self.snippets) == set(other.snippets)
                and self._meta_str() == other._meta_str()
        )

    def __hash__(self):
        return int(
            self._md5_hash((self.url, tuple(sorted(self.snippets)), self._meta_str())),
            16,
        )

    def _meta_str(self):
        """Generate a string representation of relevant meta information."""
        return f"Question: {self.meta.get('question', '')}, Query: {self.meta.get('query', '')}"

    def _md5_hash(self, value):
        """Generate an MD5 hash for a given value."""
        if isinstance(value, (dict, list, tuple)):
            value = json.dumps(value, sort_keys=True)
        return hashlib.md5(str(value).encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, info_dict):
        """Create a Information object from a dictionary.
           Usage: info = Information.from_dict(storm_info_dict)

        Args:
            info_dict (dict): A dictionary containing keys 'url',
                              'snippets', and 'title' corresponding to the object's attributes.

        Returns:
            Information: An instance of Information.
        """
        info = cls(
            url=info_dict["url"],
            snippets=info_dict["snippets"],
            title=info_dict["title"],
            meta=info_dict.get("meta", None),
        )
        info.citation_uuid = int(info_dict.get("citation_uuid", -1))
        return info

    def to_dict(self):
        return {
            "url": self.url,
            "snippets": self.snippets,
            "title": self.title,
        }


class LMConfigs(ABC):
    """Abstract base class for language model configurations of the knowledge curation engine.

    The language model used for each part should be declared with a suffix '_lm' in the attribute name.
    """

    def __init__(self):
        pass

    def init_check(self):
        for attr_name in self.__dict__:
            if "_lm" in attr_name and getattr(self, attr_name) is None:
                logging.warning(
                    f"Language model for {attr_name} is not initialized. Please call set_{attr_name}()"
                )

    def collect_and_reset_lm_history(self):
        history = []
        for attr_name in self.__dict__:
            if "_lm" in attr_name and hasattr(getattr(self, attr_name), "history"):
                history.extend(getattr(self, attr_name).history)
                getattr(self, attr_name).history = []

        return history

    def collect_and_reset_lm_usage(self):
        combined_usage = []
        for attr_name in self.__dict__:
            if "_lm" in attr_name and hasattr(
                    getattr(self, attr_name), "get_usage_and_reset"
            ):
                combined_usage.append(getattr(self, attr_name).get_usage_and_reset())

        model_name_to_usage = {}
        for usage in combined_usage:
            for model_name, tokens in usage.items():
                if model_name not in model_name_to_usage:
                    model_name_to_usage[model_name] = tokens
                else:
                    model_name_to_usage[model_name]["prompt_tokens"] += tokens[
                        "prompt_tokens"
                    ]
                    model_name_to_usage[model_name]["completion_tokens"] += tokens[
                        "completion_tokens"
                    ]

        return model_name_to_usage

    def log(self):
        return OrderedDict(
            {
                attr_name: getattr(self, attr_name).kwargs
                for attr_name in self.__dict__
                if "_lm" in attr_name and hasattr(getattr(self, attr_name), "kwargs")
            }
        )


class Engine(ABC):
    def __init__(self, lm_configs: LMConfigs):
        self.lm_configs = lm_configs
        self.time = {}
        self.lm_cost = {}  # Cost of language models measured by in/out tokens.
        self.rm_cost = {}  # Cost of retrievers measured by number of queries.

    def log_execution_time_and_lm_rm_usage(self, func):
        """Decorator to log the execution time, language model usage, and retrieval model usage of a function."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            self.time[func.__name__] = execution_time
            logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
            self.lm_cost[func.__name__] = self.lm_configs.collect_and_reset_lm_usage()
            if hasattr(self, "retriever"):
                self.rm_cost[func.__name__] = (
                    self.retriever.collect_and_reset_rm_usage()
                )
            return result

        return wrapper

    def apply_decorators(self):
        """Apply decorators to methods that need them."""
        methods_to_decorate = [
            method_name
            for method_name in dir(self)
            if callable(getattr(self, method_name)) and method_name.startswith("run_")
        ]
        for method_name in methods_to_decorate:
            original_method = getattr(self, method_name)
            decorated_method = self.log_execution_time_and_lm_rm_usage(original_method)
            setattr(self, method_name, decorated_method)

    @abstractmethod
    def run_knowledge_curation_module(self, **kwargs):
        pass

    @abstractmethod
    def run_outline_generation_module(self, **kwarg):
        pass

    @abstractmethod
    def run_article_generation_module(self, **kwarg):
        pass

    @abstractmethod
    def run_article_polishing_module(self, **kwarg):
        pass

    @abstractmethod
    def run(self, **kwargs):
        pass

    def summary(self):
        print("***** Execution time *****")
        for k, v in self.time.items():
            print(f"{k}: {v:.4f} seconds")

        print("***** Token usage of language models: *****")
        for k, v in self.lm_cost.items():
            print(f"{k}")
            for model_name, tokens in v.items():
                print(f"    {model_name}: {tokens}")

        print("***** Number of queries of retrieval models: *****")
        for k, v in self.rm_cost.items():
            print(f"{k}: {v}")

    def reset(self):
        self.time = {}
        self.lm_cost = {}
        self.rm_cost = {}
