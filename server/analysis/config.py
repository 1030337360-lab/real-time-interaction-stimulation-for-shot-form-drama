"""
配置文件 - 视频分析服务
支持多模型：通义千问 / 豆包 Doubao (火山方舟 Ark)
"""
import os


class Config:
    # ========== 路径配置 ==========
    VIDEO_DIR = r"D:\video_data\videos"
    OUTPUT_DIR = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\database"
    FRAME_DIR = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\analysis\frames"
    AUDIO_DIR = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\analysis\audio"

    # ========== 模型选择 ==========
    # 可选值: "qwen" 或 "doubao"
    ACTIVE_MODEL_PROVIDER = "doubao"

    # ========== 通义千问 (Qwen) 配置 ==========
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    QWEN_VL_MODEL = "qwen-vl-plus"
    QWEN_LLM_MODEL = "qwen-plus"
    QWEN_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"

    # ========== 豆包 Doubao (火山方舟 Ark) 配置 ==========
    # OpenAI兼容格式, 端点: https://ark.cn-beijing.volces.com/api/v3
    DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
    DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_VL_MODEL = os.getenv("DOUBAO_EP", "")
    DOUBAO_LLM_MODEL = os.getenv("DOUBAO_EP", "")

    # ========== 抽帧配置 ==========
    FRAMES_PER_EPISODE = 30
    FRAME_INTERVAL_SECONDS = 5
    FRAME_RATE = 1
    USE_CACHE = True

    # ========== 文件路径配置 ==========
    LOWDB_PATH = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\database\drama.json"
    ANALYSIS_RESULTS_PATH = os.path.join(OUTPUT_DIR, "analysis_results.json")
    GRAPH_FILE = os.path.join(OUTPUT_DIR, "character_graph_global.json")
    CACHE_DIR = os.path.join(
        r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\analysis",
        "cache"
    )

    # ========== 音频分析配置 ==========
    AUDIO_ENABLED = True
    AUDIO_DEVICE = "cuda"
