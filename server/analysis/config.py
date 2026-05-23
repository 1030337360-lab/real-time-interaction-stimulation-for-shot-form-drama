"""
配置文件 - 视频分析服务
"""
import os

class Config:
    VIDEO_DIR = r"D:\video_data\videos"

    OUTPUT_DIR = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\database"

    FRAME_DIR = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\analysis\frames"

    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")

    QWEN_MODEL = "qwen-vl-plus"

    FRAMES_PER_EPISODE = 30

    FRAME_RATE = 1

    USE_CACHE = True

    LOWDB_PATH = r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\database\drama.json"

    ANALYSIS_RESULTS_PATH = os.path.join(OUTPUT_DIR, "analysis_results.json")

    GRAPH_FILE = os.path.join(OUTPUT_DIR, "character_graph_global.json")

    CACHE_DIR = os.path.join(r"D:\mlcode\real-time-interaction-stimulation-for-shot-form-drama\server\analysis", "cache")
