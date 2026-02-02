import ollama
import json
import logging
import re
from typing import List, Dict, Any, Optional

class LLMProcessor:
    """
    LLM-Agent: 修仙文案官
    通过 Ollama (qwen2.5:7b) 识别文本中的成语并纠错
    """
    def __init__(self, model: str = "qwen2.5:7b", batch_size: int = 15):
        self.logger = logging.getLogger("LLMProcessor")
        self.model = model
        self.batch_size = batch_size
        self.system_prompt = (
            "你是一个精通成语的修仙文案官。你的任务是从给定的语音转录文本中提取成语。\n"
            "由于文本是语音识别(STT)生成的，可能存在同音错别字，请结合上下文语义进行修正。\n\n"
            "要求：\n"
            "1. 识别文本中的所有成语。\n"
            "2. 修正错别字（如 '落黄而逃' 修正为 '落荒而逃'）。\n"
            "3. 严格返回以下 JSON 格式的列表，不要包含任何其他文字：\n"
            "[{\"word\": \"修正后的成语\", \"original\": \"原始文本\", \"index\": 文本片段索引}]\n"
            "4. 如果没有发现成语，返回空列表 []。"
        )

    def process_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理文本片段
        :param segments: WhisperX 的 segments 列表
        :return: 过滤后的成语信息列表
        """
        all_found_idioms = []
        
        # 分批处理以节省上下文开销
        for i in range(0, len(segments), self.batch_size):
            batch = segments[i:i+self.batch_size]
            prompt_content = "\n".join([f"[{idx+i}] {seg['text']}" for idx, seg in enumerate(batch)])
            
            self.logger.info(f"正在通过 LLM 处理批次: {i} ~ {i+len(batch)}")
            
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {'role': 'system', 'content': self.system_prompt},
                        {'role': 'user', 'content': f"请识别以下文本中的成语：\n{prompt_content}"}
                    ],
                    options={'temperature': 0.1} # 降低随机性
                )
                
                content = response['message']['content']
                # 提取 JSON 部分
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    idioms = json.loads(json_match.group())
                    # 为识别出的成语添加对应的时间戳信息
                    for idiom in idioms:
                        idx = idiom.get('index')
                        if idx is not None and i <= idx < i + len(batch):
                            # 关联 Whisper 的原始时间戳
                            orig_seg = segments[idx]
                            idiom['start'] = orig_seg.get('start')
                            idiom['end'] = orig_seg.get('end')
                            all_found_idioms.append(idiom)
                
            except Exception as e:
                self.logger.error(f"LLM 处理批次失败: {str(e)}")
                continue
                
        self.logger.info(f"LLM 识别完成，共发现 {len(all_found_idioms)} 个成语")
        return all_found_idioms

    def save_idioms(self, idioms: List[Dict[str, Any]], output_path: str):
        """保存识别出的成语到 JSON"""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(idioms, f, ensure_ascii=False, indent=2)
            self.logger.info(f"成语列表已保存至: {output_path}")
        except Exception as e:
            self.logger.error(f"保存成语列表失败: {str(e)}")

if __name__ == "__main__":
    # 调试代码
    logging.basicConfig(level=logging.INFO)
    print("LLMProcessor module loaded.")
