import whisperx
import torch
import json
import os
import logging
import gc
import functools
from typing import Dict, List, Any, Optional

# 彻底修复 PyTorch 2.6+ 默认 weights_only=True 导致无法加载模型的问题
# 通过 Monkeypatch torch.load 强制默认 weights_only=False
_original_torch_load = torch.load
@functools.wraps(_original_torch_load)
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

class STTEngine:
    """
    STT-Agent: 使用 WhisperX 进行语音识别与单词级对齐
    适配 CUDA 12.8，支持 VAD 过滤和毫秒级时间戳获取
    """
    def __init__(
        self, 
        model_size: str = "base", 
        device: str = "cuda", 
        compute_type: str = None,
        batch_size: int = 16
    ):
        self.logger = logging.getLogger("STTEngine")
        self.device = device
        
        # 自动选择合适的计算类型
        if compute_type is None:
            self.compute_type = "float16" if device == "cuda" else "int8"
        else:
            self.compute_type = compute_type
            
        self.model_size = model_size
        self.batch_size = batch_size
        
        self.model = None
        self.align_model = None
        self.align_metadata = None
        
        self.logger.info(f"STTEngine 初始化: model={model_size}, device={device}, compute={compute_type}")

    def load_model(self):
        """加载 WhisperX 主模型"""
        if self.model is None:
            self.logger.info(f"正在加载 WhisperX 模型: {self.model_size}...")
            try:
                self.model = whisperx.load_model(
                    self.model_size, 
                    self.device, 
                    compute_type=self.compute_type,
                    download_root="models/whisperx"
                )
                self.logger.info("WhisperX 模型加载成功")
            except Exception as e:
                self.logger.error(f"WhisperX 模型加载失败: {str(e)}")
                raise

    def transcribe(self, audio_path: str, language: str = "zh") -> Dict[str, Any]:
        """
        执行转录与对齐
        1. 语音转录 (ASR)
        2. 强制对齐 (Alignment)
        """
        self.load_model()
        
        try:
            self.logger.info(f"开始处理音频: {audio_path}")
            audio = whisperx.load_audio(audio_path)
            
            # 1. Transcribe with Whisper
            self.logger.info("正在进行 ASR 转录...")
            result = self.model.transcribe(audio, batch_size=self.batch_size, language=language)
            
            # 2. Align whisper output
            self.logger.info(f"正在加载对齐模型 (语言: {language})...")
            model_a, metadata = whisperx.load_align_model(
                language_code=language, 
                device=self.device
            )
            
            self.logger.info("正在执行单词级对齐...")
            aligned_result = whisperx.align(
                result["segments"], 
                model_a, 
                metadata, 
                audio, 
                self.device, 
                return_char_alignments=False
            )
            
            # 释放对齐模型显存
            del model_a
            del metadata
            gc.collect()
            torch.cuda.empty_cache()
            
            self.logger.info("音频转录与对齐完成")
            return aligned_result
            
        except Exception as e:
            self.logger.error(f"STT 处理流程出错: {str(e)}")
            raise

    def save_results(self, result: Dict[str, Any], output_path: str):
        """保存转录结果到 JSON 文件"""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            self.logger.info(f"结果已保存至: {output_path}")
        except Exception as e:
            self.logger.error(f"保存结果失败: {str(e)}")

    def cleanup(self):
        """释放显存资源"""
        if self.model is not None:
            del self.model
            self.model = None
        gc.collect()
        torch.cuda.empty_cache()
        self.logger.info("STTEngine 资源已释放")

if __name__ == "__main__":
    # 调试代码
    logging.basicConfig(level=logging.INFO)
    # engine = STTEngine(model_size="tiny") # 快速测试
    print("STTEngine module loaded.")
