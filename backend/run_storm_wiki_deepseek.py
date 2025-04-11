"""
STORM Wiki pipeline powered by DeepSeek models and You.com or Bing search engine.
You need to set up the following environment variables to run this script:
    - DEEPSEEK_API_KEY: DeepSeek API key
    - DEEPSEEK_API_BASE: DeepSeek API base URL (default is https://api.deepseek.com)
    - YDC_API_KEY: You.com API key; BING_SEARCH_API_KEY: Bing Search API key, SERPER_API_KEY: Serper API key, BRAVE_API_KEY: Brave API key, or TAVILY_API_KEY: Tavily API key

Output will be structured as below
args.output_dir/
    topic_name/  # topic_name will follow convention of underscore-connected topic name w/o space and slash
            conversation_log.json           #信息寻求对话日志
            raw_search_results.json         #搜索引擎的原始搜索结果
            direct_gen_outline.txt          #使用LLM的参数知识直接生成大纲
            storm_gen_outline.txt           #根据收集到的信息完善大纲
            url_to_info.json                #最后一篇文章中使用的源代码
            storm_gen_article.txt           #已生成最终文章
            storm_gen_article_polished.txt  #已抛光的最终文章（如果args.do_polished_article为True）
"""

import logging
import os
from argparse import ArgumentParser
from dotenv import load_dotenv

from knowledge_storm import (
    STORMWikiRunnerArguments,
    STORMWikiRunner,
    STORMWikiLMConfigs,
)
from knowledge_storm.lm import DeepSeekModel
from knowledge_storm.rm import (
    GoogleSearch,
    BochaRM
)

load_dotenv()


def sanitize_topic(topic):
    """
    Sanitize the topic name for use in file names.
    Remove or replace characters that are not allowed in file names.
    """
    # Replace spaces with underscores
    topic = topic.replace(" ", "_")

    # Remove any character that isn't alphanumeric, underscore, or hyphen
    # topic = re.sub(r"[^a-zA-Z0-9_-]", "", topic)

    # Ensure the topic isn't empty after sanitization
    if not topic:
        topic = "unnamed_topic"

    return topic


def main(args):
    lm_configs = STORMWikiLMConfigs()

    logger = logging.getLogger(__name__)

    # Ensure DEEPSEEK_API_KEY is set
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise ValueError(
            "DEEPSEEK_API_KEY environment variable is not set. Please set it in your secrets.toml file."
        )

    deepseek_kwargs = {
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "api_base": os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
        "temperature": args.temperature,
        "top_p": args.top_p,
    }

    # DeepSeek offers two main models: 'deepseek-chat' for general tasks and 'deepseek-coder' for coding tasks
    # Users can choose the appropriate model based on their needs
    conv_simulator_lm = DeepSeekModel(
        model=args.model, max_tokens=500, **deepseek_kwargs
    )
    question_asker_lm = DeepSeekModel(
        model=args.model, max_tokens=500, **deepseek_kwargs
    )
    outline_gen_lm = DeepSeekModel(model=args.model, max_tokens=400, **deepseek_kwargs)
    article_gen_lm = DeepSeekModel(model=args.model, max_tokens=700, **deepseek_kwargs)
    article_polish_lm = DeepSeekModel(
        model=args.model, max_tokens=4000, **deepseek_kwargs
    )

    lm_configs.set_conv_simulator_lm(conv_simulator_lm)
    lm_configs.set_question_asker_lm(question_asker_lm)
    lm_configs.set_outline_gen_lm(outline_gen_lm)
    lm_configs.set_article_gen_lm(article_gen_lm)
    lm_configs.set_article_polish_lm(article_polish_lm)

    engine_args = STORMWikiRunnerArguments(
        output_dir=args.output_dir,
        max_conv_turn=args.max_conv_turn,
        max_perspective=args.max_perspective,
        search_top_k=args.search_top_k,
        max_thread_num=args.max_thread_num,
    )

    # STORM is a knowledge curation system which consumes information from the retrieval module.
    # Currently, the information source is the Internet and we use search engine API as the retrieval module.
    match args.retriever:
        case "google":
            rm = GoogleSearch(
                google_search_api_key=os.getenv("GOOGLE_API_KEY"),
                k=engine_args.search_top_k,
            )
        case "bocha":
            rm = BochaRM(
                bocha_search_api=os.getenv("BOCHA_API_KEY"),
                k=engine_args.search_top_k,
            )
        case _:
            raise ValueError(
                f'Invalid retriever: {args.retriever}. Choose either "bing", "you", "brave", "duckduckgo", "serper", "tavily", or "searxng"'
            )

    runner = STORMWikiRunner(engine_args, lm_configs, rm)

    topic = input("Topic: ")
    sanitized_topic = sanitize_topic(topic)

    try:
        runner.run(
            topic=sanitized_topic,
            do_research=args.do_research,
            do_generate_outline=args.do_generate_outline,
            do_generate_article=args.do_generate_article,
            do_polish_article=args.do_polish_article,
            remove_duplicate=args.remove_duplicate,
        )
        runner.post_run()
        runner.summary()
    except Exception as e:
        logger.exception(f"An error occurred: {str(e)}")
        raise


if __name__ == "__main__":
    parser = ArgumentParser()
    # global arguments
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./results/deepseek",
        help="Directory to store the outputs.",
    )
    parser.add_argument(
        "--max-thread-num",
        type=int,
        default=3,
        help="Maximum number of threads to use. The information seeking part and the article generation"
             "part can speed up by using multiple threads. Consider reducing it if keep getting "
             '"Exceed rate limit" error when calling LM API.',
    )
    parser.add_argument(
        "--retriever",
        type=str,
        choices=["bing", "you", "brave", "serper", "duckduckgo", "tavily", "searxng", "google"],
        default="bocha",
        help="The search engine API to use for retrieving information.",
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=["deepseek-chat", "deepseek-coder"],
        default="deepseek-chat",
        help='DeepSeek model to use. "deepseek-chat" for general tasks, "deepseek-coder" for coding tasks.',
    )
    parser.add_argument(
        "--temperature", type=float, default=1.0, help="Sampling temperature to use."
    )
    parser.add_argument(
        "--top_p", type=float, default=0.9, help="Top-p sampling parameter."
    )
    # stage of the pipeline
    parser.add_argument(
        "--do-research",
        action="store_true",
        help="If True, simulate conversation to research the topic; otherwise, load the results.",
    )
    parser.add_argument(
        "--do-generate-outline",
        action="store_true",
        help="If True, generate an outline for the topic; otherwise, load the results.",
    )
    parser.add_argument(
        "--do-generate-article",
        action="store_true",
        help="If True, generate an article for the topic; otherwise, load the results.",
    )
    parser.add_argument(
        "--do-polish-article",
        action="store_true",
        help="If True, polish the article by adding a summarization section and (optionally) removing "
             "duplicate content.",
    )
    # hyperparameters for the pre-writing stage
    parser.add_argument(
        "--max-conv-turn",
        type=int,
        default=3,
        help="Maximum number of questions in conversational question asking.",
    )
    parser.add_argument(
        "--max-perspective",
        type=int,
        default=3,
        help="Maximum number of perspectives to consider in perspective-guided question asking.",
    )
    parser.add_argument(
        "--search-top-k",
        type=int,
        default=3,
        help="Top k search results to consider for each search query.",
    )
    # hyperparameters for the writing stage
    parser.add_argument(
        "--retrieve-top-k",
        type=int,
        default=3,
        help="Top k collected references for each section title.",
    )
    parser.add_argument(
        "--remove-duplicate",
        action="store_true",
        help="If True, remove duplicate content from the article.",
    )

    main(parser.parse_args())
