# X No Y Video Stabilizer for Windows

> 只稳左右（X 轴），不碰上下。Stabilize left–right shake only, leave vertical motion untouched.
>
> GitHub: https://github.com/KolaKater/-X-No-Y-Video-Stabilizer

A Windows GUI tool for stabilizing **horizontal (X-only) shake** in old / handheld videos, with foreground / background / global reference modes and mesh warp. Built with Python + FFmpeg + OpenCV. Outputs MP4 (H.265) or stabilized frame sequences.

一个 Windows 图形界面工具，专门修**左右抖动**，不修上下抖动。支持前景 / 背景 / 全局三种参考 + 网格变形，Python + FFmpeg + OpenCV，输出 MP4（H.265）或稳定后的帧序列。

---

## Features / 功能

- **X-only stabilization / 只稳左右** — vertical motion is never touched, no vertical drift, no wobble from vertical correction. 只修左右，上下完全不动，不会越修越飘。
- **Two engines / 双引擎**
  - **FFmpeg `vidstab`** — fast, `.trf` is filtered to keep X only. 速度快，`.trf` 已过滤为只保留 X。
  - **OpenCV** — feature tracking (LK optical flow) + smoothing, works when FFmpeg struggles. 特征点跟踪 + 平滑，FFmpeg 不好使时用它。
- **Reference mode / 参考模式** — `Foreground` (前景) / `Background` (背景) / `Global` (全局). Stabilize on what matters: a walking person, a static background, or the whole frame. 前景修人、背景修景、全局修整体。
- **Mesh warp / 网格变形** — `Off` / `Light` / `Medium` / `Heavy`. Corrects parallax in old videos where foreground and background move differently. 老视频前后景视差大时用，变形越重，视差修得越多。
- **Original-size output / 原尺寸输出** — crop 5 px per side (e.g. 1920×1080 → 1910×1080), then fill the missing edge with a blurred copy of the frame, so output stays 1920×1080. 每边裁 5px，再用模糊帧补边，输出保持原尺寸。
- **Frame sequences / 帧序列** — drag in a folder of frames, output stabilized frames (JPG, quality 95) or MP4 at 23.976 / 24 / 25 / 29.97 / 30 / 50 / 60 / 120 fps. 拖入帧序列文件夹，输出稳定帧或指定帧率的 MP4。
- **Audio preserved / 保留音频** — silent videos also work. 有声 / 无声都能处理，音频原样保留。
- **12 languages / 12 种语言** — 中文 / English / Deutsch / Français / Español / Italiano / Português / 日本語 / 한국어 / Nederlands / العربية / Türkçe. No Russian. 无俄语。Languages live in `bin/stablizer_languages.json`, editable without rebuilding. 语言在 `bin/stablizer_languages.json`，改了不用重新打包。
- **Progress + debug log / 进度 + 日志** — progress bar with % (estimation → stabilization → muxing), scrolling status, `vid_stablizer_debug.log` in the program folder (cleared on each startup). 进度条带百分比（估计 → 稳定 → 合成），状态滚动显示，日志在程序目录，启动时清空。

## Screenshots / 截图

> Put your screenshots here. 截图放这里（建议：主界面 + 处理中 + 结果对比）。

| Main Window / 主界面 | Running / 处理中 |
|---|---|
| [Main](docs/screenshot-main.png) | [Running](docs/screenshot-running.png) |

## Download / 下载

**No Python needed. 不用装 Python。**

1. Go to [**Releases**](https://github.com/KolaKater/-X-No-Y-Video-Stabilizer/releases) → download the latest `Stablizer-Windows.zip`.
   去 Releases 页面下载最新版 `Stablizer-Windows.zip`。
2. Unzip it anywhere, keep the folder structure (do **not** delete `bin/`).
   解压到任意位置，保持文件夹结构，**不要删 `bin/`**。
3. Double-click `Stablizer.exe`.
   双击 `Stablizer.exe`。

> `bin/` contains `ffmpeg.exe`, `ffprobe.exe`, `stablizer_languages.json` — the EXE needs them next to it.
> `bin/` 里有 `ffmpeg.exe`、`ffprobe.exe`、`stablizer_languages.json`，EXE 需要它们在旁边。

## Usage / 使用

1. Drag a video (MP4 / MKV / …) or a **frame-sequence folder** into the file list.
   把视频或**帧序列文件夹**拖进文件列表。
2. Pick **Method** (FFmpeg / OpenCV), **Reference** (Foreground / Background / Global), **Mesh warp** (Off / Light / Medium / Heavy).
   选方法、参考、网格变形。
3. Pick **Smoothing** (5–100, default 30), **Output size** (Original / Cropped), **Output** (MP4 / Frames), **FPS**.
   选平滑度（默认 30）、输出尺寸、输出格式、帧率。
4. Click **Start**. Output is written next to the source, named like:
   点 **Start**。输出写在源文件旁边，命名如：
   - `MyVideo_ffmpeg_stablized_1920x1080_24fps.mp4`
   - `MyVideo_opencv_stablized_1920x1080_24fps.mp4`
5. Click the status line to open the output. 点状态行可打开输出文件。

**Tips / 建议：**

- Walking shake / handheld: start with `OpenCV + Foreground + Mesh Medium + Smoothing 40`.
  走路抖动 / 手持：先试 `OpenCV + 前景 + 网格 Medium + 平滑 40`。
- Fast preview: try `FFmpeg` first, it is much faster.
  先用 FFmpeg 快速预览，它快很多。
- Old video with strong parallax: `Mesh Heavy` helps, but it is slower.
  老视频视差大：`Mesh Heavy` 有用，但更慢。

## Build from source / 从源码打包 EXE

Requires Windows + Python 3.11. 需要 Windows + Python 3.11。

```bat
REM 1. Put ffmpeg.exe / ffprobe.exe in bin\
REM    把 ffmpeg.exe / ffprobe.exe 放进 bin\

REM 2. Build (double-click, or run in CMD)
REM    打包（双击或在 CMD 里跑）
build_exe.bat

REM 3. Output / 输出
REM    dist\Stablizer\Stablizer.exe   (recommended, onedir)
REM    or: build_exe.bat onefile  ->  dist\Stablizer.exe (single file, slower startup)
```

Or manually / 手动打包：

```bat
pip install opencv-python numpy pillow pyinstaller
pyinstaller --noconfirm --clean --windowed --name Stablizer ^
    --add-data "bin;bin" ^
    --hidden-import cv2 --hidden-import numpy --hidden-import PIL ^
    --collect-all cv2 --collect-all numpy ^
    stablizer_gui.py
```

> Use **onedir** (default) for daily use: faster startup, less likely to trip antivirus, and `bin\ffmpeg.exe` stays a real file.
> 日常用 **onedir**（默认）：启动更快，不容易被杀毒软件误报，`bin\ffmpeg.exe` 也是真实文件。
> `onefile` packs everything into one EXE but extracts ~200 MB to a temp folder on every launch.
> `onefile` 是单个 EXE，但每次启动都要解压约 200 MB 到临时目录。

## Project structure / 目录结构

```
ffmpeg/
├── stablizer_gui.py            # GUI (Tkinter, drag & drop, 12 languages)
├── vid_stablizer.py            # Stabilization core (FFmpeg vidstab + OpenCV X-only)
├── Lanch_stablizer_gui.bat     # Launch from source (pythonw, no console window)
├── build_exe.bat               # Build EXE with PyInstaller
├── requirements.txt
├── README.md
└── bin/
    ├── ffmpeg.exe              # Bundled FFmpeg (Gyan build)
    ├── ffprobe.exe             # Bundled FFprobe
    ├── stablizer_languages.json  # 12 languages, editable
    └── stablizer_gui_config.json # Saved settings (auto-created)
```

## Settings / 设置

- Smoothing: 5–100, default 30. 平滑度默认 30。
- Crop: 5 px per side. 裁边每边 5px。
- Output video: MP4, H.265 (`libx265`, CRF 18), ~quality 95. 输出视频 MP4，H.265，CRF 18。
- Output frames: JPG, quality 95. 输出帧 JPG，质量 95。
- Video FPS: from source. 视频帧率：跟源视频。
- Frame-sequence FPS: 23.976 / 24 / 25 / 29.97 / 30 / 50 / 60 / 120. 帧序列帧率可选。
- Config is saved to `bin/stablizer_gui_config.json`. 设置保存在 `bin/stablizer_gui_config.json`。

## Troubleshooting / 常见问题

| Problem / 问题 | Fix / 解决 |
|---|---|
| EXE says ffmpeg not found / EXE 提示找不到 ffmpeg | Keep `bin\ffmpeg.exe` next to `Stablizer.exe`, do not move the EXE alone. 把 `bin\` 整个跟 EXE 放一起，不要只拷一个 EXE。 |
| Progress stuck at 0% for a while / 进度长时间 0% | Normal on long videos: estimation runs first (0–50%). `Mesh Heavy` on 1080p is slow, wait. 长视频正常：先算估计（0–50%），`Mesh Heavy` 在 1080p 上本来就慢，等一下。 |
| Output looks wavy / 输出发飘 | Lower smoothing, or switch Reference (Foreground ↔ Background), or Mesh → Light. 降平滑度，或换参考（前景 ↔ 背景），或网格改 Light。 |
| No effect / 没效果 | Check Method: FFmpeg is subtle on heavy shake, try OpenCV + Mesh Medium/Heavy. 换 OpenCV + 网格 Medium/Heavy。 |
| Antivirus flags the EXE / 杀毒软件报毒 | Rebuild from source with `build_exe.bat`, or add the folder to exclusions. 用 `build_exe.bat` 自己重新打包，或把文件夹加入白名单。 |

Debug log: `vid_stablizer_debug.log` in the program folder (next to the EXE). Paste it when reporting an issue.
调试日志：程序目录下的 `vid_stablizer_debug.log`，报问题时贴它。

## License / 许可证

MIT — see `LICENSE` (add one before publishing, e.g. `MIT License`).
MIT，发布前加一个 `LICENSE` 文件。

## Credits / 致谢

- FFmpeg + `vidstab` filter — https://ffmpeg.org
- OpenCV — https://opencv.org
- FFmpeg Windows builds by Gyan — https://www.gyan.dev/ffmpeg/builds/

---
*Repo: https://github.com/KolaKater/-X-No-Y-Video-Stabilizer — © 2026 Tony Lin*
*仓库：https://github.com/KolaKater/-X-No-Y-Video-Stabilizer — © 2026 Tony Lin*
