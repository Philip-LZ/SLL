"""通用工具函数模块"""
import json
import logging
import os
import pickle
import re
import regex
import sys
from typing import List, Dict
from tqdm import tqdm


class ArticleTextProcessing:
    @staticmethod
    def limit_word_count_preserve_newline(input_string, max_word_count):
        """
        将输入字符串的字数限制在指定的最大值，同时保持完整行的完整性。

        该函数在不超过最大字数的最近单词处截断输入字符串，确保输出中不包括部分行。
        单词被定义为由空格分隔的文本，行被定义为由换行符分隔的文本。

        Args：
        input_string（str）：要截断的字符串。此字符串可能包含多行。
        max_word_count（int）：截断字符串中允许的最大单词数。

        returns：
        str：字数限制为`max_word_count `的截断字符串，保留完整行。
        """

        word_count = 0
        limited_string = ""

        for word in input_string.split("\n"):
            line_words = word.split()
            for lw in line_words:
                if word_count < max_word_count:
                    limited_string += lw + " "
                    word_count += 1
                else:
                    break
            if word_count >= max_word_count:
                break
            limited_string = limited_string.strip() + "\n"

        return limited_string.strip()

    @staticmethod
    def remove_citations(s):
        """
        删除给定字符串中的所有引用。引用被假定为方括号内的数字格式，如[1]、[2]或[1,2]等。
        此函数搜索所有出现的此类模式并将其删除，返回清理后的字符串。

        Args:
        s（str）：要从中删除引用的字符串。

        returns
        str：删除了所有引用模式的字符串。
        """

        return re.sub(r"\[\d+(?:,\s*\d+)*\]", "", s)

    @staticmethod
    def parse_citation_indices(s):
        """
        从提供的内容字符串中提取引文索引，并将其作为整数列表返回。

        Args：
        content（str）：包含引用的内容字符串，格式为[number]。

        returns：
        List[int]：按出现顺序从内容中提取的唯一引用索引列表。
        """
        matches = re.findall(r"\[\d+\]", s)
        return [int(index[1:-1]) for index in matches]

    @staticmethod
    def remove_uncompleted_sentences_with_citations(text):
        """
        从输入文本中删除未完成的句子和独立引用。句子已识别通过它们的结束标点符号（.！？），可以选择在方括号中加上引用（例如“[1]”）。
        分组引用（例如“[1,2]”）被拆分为单独的引用（例如，“[1][2]”）。最多只能发送文本并保留最后一个完整句子及其引用。

        Args：
        text（str）：输入文本，从中删除未完成的句子及其引用。

        退货：
        str：已处理的字符串，其中删除了未完成的句子和独立的引用，只留下
        完整的句子及其相关引用（如果有的话）。
        """

        # Convert citations like [1, 2, 3] to [1][2][3].
        def replace_with_individual_brackets(match):
            numbers = match.group(1).split(", ")
            return " ".join(f"[{n}]" for n in numbers)

        # 对各组引文进行重复和排序。
        def deduplicate_group(match):
            citations = match.group(0)
            unique_citations = list(set(re.findall(r"\[\d+\]", citations)))
            sorted_citations = sorted(
                unique_citations, key=lambda x: int(x.strip("[]"))
            )
            # 以字符串形式返回排序后的唯一引用
            return "".join(sorted_citations)

        text = re.sub(r"\[([0-9, ]+)\]", replace_with_individual_brackets, text)
        text = re.sub(r"(\[\d+\])+", deduplicate_group, text)
        eos_pattern = r"([。！？])\s*(\[\d+\])?\s*"
        matches = list(re.finditer(eos_pattern, text))
        if matches:
            last_match = matches[-1]
            text = text[: last_match.end()].strip()

        return text

    @staticmethod
    def clean_up_citation(conv):
        for turn in conv.dlg_history:
            if "References:" in turn.agent_utterance:
                turn.agent_utterance = turn.agent_utterance[
                    : turn.agent_utterance.find("References:")
                ]
            if "Sources:" in turn.agent_utterance:
                turn.agent_utterance = turn.agent_utterance[
                    : turn.agent_utterance.find("Sources:")
                ]
            turn.agent_utterance = turn.agent_utterance.replace("Answer:", "").strip()
            try:
                max_ref_num = max(
                    [int(x) for x in re.findall(r"\[(\d+)\]", turn.agent_utterance)]
                )
            except Exception as e:
                max_ref_num = 0
            if max_ref_num > len(turn.search_results):
                for i in range(len(turn.search_results), max_ref_num + 1):
                    turn.agent_utterance = turn.agent_utterance.replace(f"[{i}]", "")
            turn.agent_utterance = (
                ArticleTextProcessing.remove_uncompleted_sentences_with_citations(
                    turn.agent_utterance
                )
            )

        return conv

    @staticmethod
    def clean_up_outline(outline, topic=""):
        output_lines = []
        current_level = 0  # To track the current section level

        for line in outline.split("\n"):
            stripped_line = line.strip()

            if topic != "" and f"# {topic.lower()}" in stripped_line.lower():
                output_lines = []

            # Check if the line is a section header
            if stripped_line.startswith("#"):
                current_level = stripped_line.count("#")
                output_lines.append(stripped_line)
            # Check if the line is a bullet point
            elif stripped_line.startswith("-"):
                subsection_header = (
                    "#" * (current_level + 1) + " " + stripped_line[1:].strip()
                )
                output_lines.append(subsection_header)

        outline = "\n".join(output_lines)

        # 移除参考文献。
        outline = re.sub(r"#[#]?参见*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]?参考*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]?注释*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]?参考文献*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]?外部链接*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]?进一步阅读*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]?摘要*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]?附录*?(?=##|$)", "", outline, flags=re.DOTALL)
        # 清理大纲中的注释
        outline = re.sub(r"\[.*?\]", "", outline)
        return outline

    @staticmethod
    def clean_up_section(text):
        """清理一个部分：
        1. 移除不完整的句子（通常由于输出令牌限制）。
        2. 对单独的引用组进行去重。
        3. 移除不必要的摘要。
        """

        paragraphs = text.split("\n")
        output_paragraphs = []
        summary_sec_flag = False
        for p in paragraphs:
            p = p.strip()
            if len(p) == 0:
                continue
            if not p.startswith("#"):
                p = ArticleTextProcessing.remove_uncompleted_sentences_with_citations(p)
            if summary_sec_flag:
                if p.startswith("#"):
                    summary_sec_flag = False
                else:
                    continue
            if (
                p.startswith("Overall")
                or p.startswith("In summary")
                or p.startswith("In conclusion")
            ):
                continue
            if "# Summary" in p or "# Conclusion" in p:
                summary_sec_flag = True
                continue
            output_paragraphs.append(p)

        # Join with '\n\n' for markdown format.
        return "\n\n".join(output_paragraphs)

    @staticmethod
    def update_citation_index(s, citation_map):
        """根据引用图更新字符串中的引用索引。"""
        for original_citation in citation_map:
            s = s.replace(
                f"[{original_citation}]", f"__PLACEHOLDER_{original_citation}__"
            )
        for original_citation, unify_citation in citation_map.items():
            s = s.replace(f"__PLACEHOLDER_{original_citation}__", f"[{unify_citation}]")

        return s

    @staticmethod
    def parse_article_into_dict(input_string):
        """
        将结构化文本解析为嵌套字典。文本的结构由类似Markdown的标题（使用'#'符号）来表示章节和小节。
        每个部分可以包含内容和进一步的嵌套小节。

        结果字典捕获了部分的层次结构，其中每个部分都由一个键（部分的标题）映射到另一个字典作为值。
        这个字典包含两个键：
        - 'content'：部分的内容
        - 'subsections'：一个字典列表，每个字典代表一个嵌套的小节
        并遵循上述相同的结构。

        参数:
            input_string (str): 要解析的结构化文本字符串。

        返回:
            一个字典，其中包含部分标题作为键，另一个字典作为值，该字典包括上面描述的'content'和'subsections'键。
        """
        lines = input_string.split("\n")
        lines = [line for line in lines if line.strip()]
        root = {"content": "", "subsections": {}}
        current_path = [(root, -1)]  # (current_dict, level)

        for line in lines:
            if line.startswith("#"):
                level = line.count("#")
                title = line.strip("# ").strip()
                new_section = {"content": "", "subsections": {}}

                # Pop from stack until find the parent level
                while current_path and current_path[-1][1] >= level:
                    current_path.pop()

                # Append new section to the nearest upper level's subsections
                current_path[-1][0]["subsections"][title] = new_section
                current_path.append((new_section, level))
            else:
                current_path[-1][0]["content"] += line + "\n"

        return root["subsections"]

class FileIOHelper:
    @staticmethod
    def dump_json(obj, file_name, encoding="utf-8"):
        with open(file_name, "w", encoding=encoding) as fw:
            json.dump(obj, fw, default=FileIOHelper.handle_non_serializable)

    @staticmethod
    def handle_non_serializable(obj):
        return "non-serializable contents"  # mark the non-serializable part

    @staticmethod
    def load_json(file_name, encoding="utf-8"):
        with open(file_name, "r", encoding=encoding) as fr:
            return json.load(fr)

    @staticmethod
    def write_str(s, path):
        with open(path, "w") as f:
            f.write(s)

    @staticmethod
    def load_str(path):
        with open(path, "r") as f:
            return "\n".join(f.readlines())

    @staticmethod
    def dump_pickle(obj, path):
        with open(path, "wb") as f:
            pickle.dump(obj, f)

    @staticmethod
    def load_pickle(path):
        with open(path, "rb") as f:
            return pickle.load(f)

