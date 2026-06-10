#!/usr/bin/env python3
"""
音频分析模块 - 独立测试脚本
用于快速诊断和测试audio_analyzer.py各个功能环节
用法:
    python test_audio.py              # 自动检测环境并运行测试
    python test_audio.py --video xxx.mp4   # 指定一个视频文件测试
    python test_audio.py --no-funasr  # 只测试降级模式
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("="*70)
print("  短剧AI分析引擎 - 音频模块测试工具")
print("="*70)
print()

# ============================================================
# 测试1: 基础环境检测
# ============================================================
print("[测试1] 环境基础检查...")
import platform
print(f"  - 操作系统: {platform.system()} {platform.release()}")
print(f"  - Python路径: {sys.executable}")
print(f"  - Python版本: {sys.version.split()[0]}")

try:
    import torch
    print(f"  - PyTorch版本: {torch.__version__}")
    print(f"  - CUDA可用: {'✅ 是' if torch.cuda.is_available() else '❌ 否 (使用CPU)'}")
    if torch.cuda.is_available():
        print(f"  - GPU设备: {torch.cuda.get_device_name(0)}")
    torch_ok = True
except ImportError:
    print("  - ❌ PyTorch未安装")
    torch_ok = False

try:
    import numpy
    print(f"  - NumPy版本: {numpy.__version__}")
    numpy_ok = True
except ImportError:
    print("  - ❌ NumPy未安装")
    numpy_ok = False

# 检查ffmpeg
import shutil
ffmpeg_path = shutil.which("ffmpeg")
if ffmpeg_path:
    print(f"  - FFmpeg: ✅ 找到于 {ffmpeg_path}")
    ffmpeg_ok = True
else:
    print("  - FFmpeg: ❌ 未找到 (请确保ffmpeg在PATH中)")
    ffmpeg_ok = False

# ============================================================
# 测试2: FunASR导入测试
# ============================================================
print()
print("[测试2] FunASR依赖库导入检查...")
funasr_ok = False
try:
    import funasr
    print(f"  - FunASR版本: {funasr.__version__}")
    funasr_ok = True
except ImportError:
    print("  - ❌ FunASR未安装")
    print("      提示: pip install funasr modelscope")

try:
    import modelscope
    print(f"  - ModelScope版本: {modelscope.__version__}")
except ImportError:
    print("  - ❌ ModelScope未安装")
    if funasr_ok:
        print("      警告: FunASR需要ModelScope才能下载模型!")

# ============================================================
# 测试3: AudioAnalyzer基础初始化测试
# ============================================================
print()
print("[测试3] AudioAnalyzer类初始化测试...")

from audio_analyzer import AudioAnalyzer

try:
    device = "cuda" if (torch_ok and torch.cuda.is_available()) else "cpu"
    print(f"  -> 创建AudioAnalyzer实例 (device={device})...")
    aa = AudioAnalyzer(device=device)
    print("  -> ✅ AudioAnalyzer实例创建成功")
except Exception as e:
    print(f"  -> ❌ 实例创建失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("="*70)
    print("  测试结果: ❌ 严重失败，请检查依赖安装")
    print("="*70)
    sys.exit(1)

# ============================================================
# 测试4: 模型加载测试
# ============================================================
print()
print("[测试4] FunASR模型加载测试 (这可能需要几分钟下载)...")
try:
    aa.load_models()
    print()
    print(f"  - is_available() = {aa.is_available()}")
    
    if aa.is_available():
        print("  -> ✅ 核心模型(VAD+ASR)加载成功!")
    else:
        print("  -> ⚠ 核心模型未完全可用 (降级模式)")
    
    models_summary = []
    models_summary.append(("VAD", aa.vad_model is not None))
    models_summary.append(("ASR", aa.asr_model is not None))
    models_summary.append(("说话人分离", aa.spk_model is not None))
    models_summary.append(("环境音分类", aa.sound_classifier is not None))
    
    for name, ok in models_summary:
        status_icon = "✅" if ok else "❌"
        print(f"    {name}: {status_icon}")

except Exception as e:
    print(f"  -> ❌ 模型加载异常: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# 测试5: 可选 - 实际视频文件测试
# ============================================================
print()
print("[测试5] 实际视频音频分析测试 (可选)...")

# 找一个测试视频
import sys as sys2
args = sys2.argv

test_video_path = None
if len(args) > 2 and args[1] == "--video":
    test_video_path = Path(args[2])
else:
    # 尝试从配置自动找
    try:
        from config import Config
        video_dir = Path(Config.VIDEO_DIR)
        if video_dir.exists():
            # 找第一个 .mp4
            print(f"  -> 自动扫描目录: {video_dir}")
            mp4_files = list(video_dir.rglob("*.mp4"))
            if mp4_files:
                test_video_path = mp4_files[0]
                print(f"  -> 自动找到测试视频: {test_video_path}")
    except Exception as e_cfg:
        print(f"  -> 自动配置查找跳过: {e_cfg}")

if test_video_path and test_video_path.exists():
    print(f"  -> 开始完整音频分析测试: {test_video_path.name}")
    try:
        result = aa.analyze_full(str(test_video_path))
        
        print()
        print("  ============= 测试结果 =============")
        print(f"    skipped: {result.get('skipped', 'N/A')}")
        print(f"    人声片段数: {result.get('total_speech_segments', 0)}")
        print(f"    有效对话数: {len(result.get('dialogue', []))}")
        
        dialogues = result.get('dialogue', [])
        if dialogues:
            print()
            print("    前5条对话示例:")
            for i, d in enumerate(dialogues[:5]):
                text_show = d.get('text', '')[:50]
                print(f"      [{i+1}] {d.get('speaker','spk0')} @ {d.get('start',0):.1f}s: \"{text_show}\"")
        
        if result.get('skipped'):
            print()
            print(f"    原因: {result.get('reason', 'unknown')}")
            if 'error' in result:
                print(f"    错误: {result['error_type']}: {result['error']}")
        
        print("  ===================================")
        print("  -> ✅ 完整视频音频分析测试通过!")
        
    except Exception as e:
        print(f"  -> ❌ 完整分析测试失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
else:
    print("  -> ⚠ 没有找到测试视频，跳过实际视频测试")
    print("     提示: 可以运行: python test_audio.py --video 你的视频.mp4")

# ============================================================
# 测试总结
# ============================================================
print()
print("="*70)
print("  测试总结")
print("="*70)

passed_count = 0
total_tests = 0

total_tests += 1
if torch_ok: passed_count +=1
print(f"  1. PyTorch环境: {'✅' if torch_ok else '❌'}")

total_tests +=1
if ffmpeg_ok: passed_count +=1
print(f"  2. FFmpeg可用: {'✅' if ffmpeg_ok else '❌'}")

total_tests +=1
if funasr_ok: passed_count +=1
print(f"  3. FunASR安装: {'✅' if funasr_ok else '❌'}")

total_tests +=1
if aa.is_available(): passed_count +=1
print(f"  4. 音频分析可用: {'✅' if aa.is_available() else '⚠️ (降级模式)'}")

print()
print(f"  总分: {passed_count}/{total_tests} 通过")
print()

if passed_count == total_tests and aa.is_available():
    print("  🎉 音频模块完全正常，可以投入使用!")
elif passed_count >= 2:
    print("  ⚠️ 部分通过，音频模块将以降级模式运行（不崩溃，跳过音频分析）")
    print("     纯视觉分析流程仍然可以正常完成!")
else:
    print("  ❌ 关键依赖缺失，请检查安装!")

print("="*70)
