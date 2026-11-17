# Easy3D · X-No-Y Stabilizer & 3D Converter

> 只稳左右（X 轴），不碰上下。Stabilize left–right shake only, leave vertical motion untouched.
> 再加 3D 格式转换 + Motion Wiggle。Plus 3D format conversion + Motion Wiggle.
>
> GitHub: https://github.com/KolaKater/-X-No-Y-Video-Stabilizer
> © 2026 Tony Lin
<img width="862" height="652" alt="Screenshot 2026-11-17 121024" src="https://github.com/user-attachments/assets/57d4d1b3-a90a-4e62-9adf-03f372c4ef66" />

一个 Windows 图形界面工具，做两件事，**分开做，不混在一起**：

1. **2D：只修左右抖动** — 视频 / 帧序列，X 轴防抖，Y 轴完全不动。
2. **3D：只做格式转换** — SBS 左右图 / 视频，swap / anaglyph / Motion，不做防抖。

A Windows GUI tool for two separate jobs, **never mixed**:

1. **2D: X-only stabilization** — videos / frame sequences, X-axis only, Y untouched.
2. **3D: format conversion only** — SBS left-right images / videos, swap / anaglyph / Motion, no stabilization.

---

## Features / 功能

### 2D · X-only stabilization / 只稳左右

- **X-only / 只稳左右** — vertical motion is never touched, no vertical drift. 只修左右，上下完全不动。
- **Two engines / 双引擎**
  - **FFmpeg `vidstab`** — fast, `.trf` is filtered to keep X only (dy / rotation = 0). 速度快，`.trf` 已过滤为只保留 X。
  - **OpenCV** — LK optical flow feature tracking + smoothing. 特征点跟踪 + 平滑。
- **Reference mode / 参考模式** — `Global` (全局) / `Foreground` (前景) / `Background` (背景).
- **Mesh warp / 网格变形** — `Off` / `Light` / `Medium` / `Heavy`, X-only, wider transition. 只做 X 向变形。
- **Smoothing / 平滑强度** — default 30, range 5–100. 默认 30，范围 5–100。
- **Original-size output / 原尺寸输出** — crop 5 px per side (e.g. 1920×1080 → 1910×1080), then fill the missing edge with a blurred copy of the frame, so output stays 1920×1080. 每边裁 5px，再用模糊帧补边，输出保持原尺寸。`Cropped` 模式则直接出 1910×1080。
- **Frame sequences / 帧序列** — drag in a folder of frames, output stabilized frames (JPG, quality 95) or MP4 at 23.976 / 24 / 25 / 29.97 / 30 / 50 / 60 / 120 fps. 拖入帧序列文件夹，输出稳定帧或指定帧率的 MP4。
- **Audio preserved / 保留音频** — silent videos also work. 有声 / 无声都能处理，音频原样保留。
- **Output / 输出** — MP4 (H.265 / libx265, CRF 18) or JPG frames (quality 95). MP4 (H.265) 或 JPG 帧（质量 95）。

### 3D · Format conversion only / 只做格式转换

> **选了 3D，防抖选项会自动锁掉。** 防抖会改 X 位移 / 做网格变形 / 模糊补边，会破坏左右眼的视差对应，看着会头晕 / 重影 / 凹凸反了。
>
> **When 3D is selected, stabilization options are auto-locked.** Stabilization changes X shift / mesh warp / blurred edges and breaks left-right disparity.
>
> 想先防抖、再转 3D，分两步跑：第一步 3D=`none` 防抖出片，第二步拿防抖后的片子再转 3D。

- **Swap / 平行眼 ↔ 斗鸡眼** — SBS 左右两半互换。`Parallel ↔ CrossEye`。视频出 `_swap.mp4`，单张图片出 `_swap.jpg`（尺寸不变）。
- **Anaglyph / SBS 转红蓝** — SBS → 红蓝（红青）单张图。`SBS → Red-Cyan`。视频出 `_anaglyph.mp4`，单张图片出 `_anaglyph.jpg`（单眼尺寸，R 取左眼，G/B 取右眼）。戴红蓝眼镜看。
- **Motion (Wiggle) / 抖动视频** — 单张 SBS 图片 → 2D 抖动视频。
  - 输入：单张 SBS 图片，如 `3836×1278`（左 1918×1278 + 右 1918×1278）或竖版 `3836×3409`（左 1918×3409 + 右 1918×3409）。
  - 输出：单眼尺寸的 2D MP4，如 `1918×1278` 或 `1918×3408`，`_motion.mp4`。
  - 画面：同一时间只显示左眼或右眼一张，每 **0.3 秒**换一次：左 → 右 → 左 → 右……来回抖，大脑觉得有深度 / 在动。
  - 时长：循环重复 **5–10 秒，默认 6 秒**（30fps 下 180 帧，每 9 帧换一次眼，换 20 次）。
  - **Motion 只能出 MP4**，选了 Motion，保存方式自动变成 MP4 并锁掉。
  - **Motion 对真实的 3D SBS 支持会比较好。Motion works best on real 3D SBS photos / videos.**
    真相机拍的 SBS，左右眼是同一场景的两个视角，几何一致，warp 能对上，6 帧循环看着是滑过去的。
    Real SBS (shot with a real stereo camera) has geometrically consistent left/right eyes, so warp aligns and the 6-frame loop looks smooth.
  - **AI 生成的 SBS 可能左右眼内容不一致。AI-generated SBS may have inconsistent left/right eyes.**
    比如 AI 两次生成的两张图，花瓣位置、形状都不一样，不是“整体挪一点”，也不是“深度视差”，是内容本身对不上。
    这种图 warp 再怎么做，中间帧也碰不到一起，`左 warp → 右 warp` 那一步还是大跳，看着还是硬。这是图本身的问题，不是帧数的问题。
    No warp can fix it if the two eyes are two separate generations with different content. Try `warp_amount=0.5`, or slow the loop, or use `anaglyph` instead.
  - 6 帧循环（warp-only，不叠加，不重影）：`1 左眼 | 2 左眼轻微往右 warp | 3 右眼轻微往左 warp | 4 右眼 | 5=3 | 6=2`，循环。
    30fps 下 6 帧 = 0.2 秒一循环，6 秒 = 30 个循环 = 180 帧。每帧只有一只眼，中间帧不是 `左+右` 叠加，所以不重影。
    6-frame loop (warp-only, no blending, no ghosting). Each frame is a single eye.
  - `warp_amount` 默认 0.35（往对面走 35%），建议 0.25–0.45，AI 图可试到 0.5。光流已平滑 + 限幅 30px，防遮挡处算飞。
- **Single image / 单张图片** — 拖入单张图片 = 一个 `[Image]` 任务，只处理这一张，不读整个文件夹。列表里显示文件名，不是文件夹名。
  - 拖文件夹 = 按文件夹里的帧序列处理（不同文件夹的帧序列不能混放）。
- **Even size / 偶数尺寸** — Motion / swap / anaglyph 输出前，宽高自动修成能被 2 整除的整数（x265 / yuv420p 要求）。如 `1918×3409 → 1918×3408`（高裁掉底边 1px）。横版、竖版 SBS 都能转，不再用宽高比 `1.6` 卡竖版。

### 界面 / UI

- **Title / 标题** — `Easy3D · X-No-Y Stabilizer & 3D Converter`。
- **Icons / 图标** — 主窗口 + About 弹窗标题栏都用 `bin\Easy3D.ico`。Window + About title bar use `bin\Easy3D.ico`.
- **File list / 文件列表** — 背景 `#23282e`（跟 `bin\Easy3D_s.png` 的底色一样，接缝看不出来），文件名白色，选中行深灰。Background `#23282e` (same as `bin\Easy3D_s.png`), white text.
- **Empty list background / 空列表背景** — 列表空时居中显示 `bin\Easy3D_s.png`，随窗口等比缩放，不拉伸变形；有文件时自动藏起来。Empty list shows `bin\Easy3D_s.png` centered, scales with window, keeps aspect.
- **About / 关于** — 自定义弹窗，标题栏图标 `Easy3D.ico`，里面显示 `Easy3D_s.png` + About 文字。
- **12 languages / 12 种语言** — 中文 / English / Deutsch / Français / Español / Italiano / Português / 日本語 / 한국어 / Nederlands / العربية / Türkçe. No Russian. 无俄语。Languages live in `bin/stablizer_languages.json`, editable without rebuilding.
- **Progress + debug log / 进度 + 调试日志** — progress bar + scrolling status, `vid_stablizer_debug.log` in project root, cleared on each startup. 进度条 + 滚动状态，调试日志在项目根目录，每次启动清空。

---

## Quick start / 快速上手

### 2D 防抖 / Stabilize

1. Double-click `Lanch_stablizer_gui.bat` (or `Stablizer.exe` after build). 双击 `Lanch_stablizer_gui.bat`（打包后是 `Stablizer.exe`）。
2. Drag videos / a folder of frames into the list. 拖视频 / 帧序列文件夹进列表。
3. 3D 模式 = `none`，选方案 / 平滑 / 参考 / Warp / 输出尺寸 / 帧率 / 保存方式。
4. Start. 点开始。输出在源文件旁边，如 `..._1910x1080_stablized.mp4` / `..._stablized.jpg`。

### 3D 转换 / Convert 3D

1. Drag **one SBS image** (or an SBS video / a folder of SBS frames) into the list. 拖**一张 SBS 图片**（或 SBS 视频 / SBS 帧文件夹）进列表。
2. 3D 模式选 `swap` / `anaglyph` / `motion`。防抖选项会自动锁掉。
3. Start. 点开始。
   - `swap` → `_swap.mp4` / `_swap.jpg`
   - `anaglyph` → `_anaglyph.mp4` / `_anaglyph.jpg`
   - `motion` → `_motion.mp4`（单眼尺寸，6 秒，每 0.3 秒换眼，只能出 MP4）

### 两步：先防抖、再转 3D / Two steps

1. Step 1: 3D=`none`，防抖出片。Stabilize first.
2. Step 2: 拿防抖后的片子，3D=`swap` / `anaglyph` / `motion`，再转一次。Then convert the stabilized output.

---

## Files / 文件结构

```
X-No-Y-Video-Stabilizer/
  stablizer_gui.py              # GUI (Tkinter)
  vid_stablizer.py              # Core: stabilization + 3D + Motion
  Lanch_stablizer_gui.bat       # Launcher (pythonw, no console)
  Debug_Lanch.bat               # Debug launcher (shows errors)
  build_exe.py / build_exe.bat  # Build EXE with PyInstaller
  README.md / LICENSE
  bin/
    Easy3D.ico                  # Window + About icon
    Easy3D_s.png                # Empty-list background + About image
    stablizer_languages.json    # 12 languages
    stablizer_gui_config.json   # Saved GUI settings
    ffmpeg.exe / ffprobe.exe    # Gyan build (not pushed to GitHub, see .gitignore)
  vid_stablizer_debug.log       # Debug log (cleared on startup)
```

- **Do NOT push `bin\ffmpeg.exe` / `bin\ffprobe.exe` to GitHub** (422MB, see `.gitignore`). 不要把 `bin\ffmpeg.exe` / `ffprobe.exe` 推到 GitHub。
- **EXE**: run `build_exe.bat` on Windows (`python -m PyInstaller`). 打包 EXE 请在 Windows 上跑 `build_exe.bat`。

## Requirements / 依赖

- Windows 10/11, Python 3.11
- `opencv-python`, `numpy`, `Pillow`, `tkinterdnd2` (see `requirements.txt`)
- FFmpeg with `libvidstab` + `libx265` (Gyan full build, in `bin\`)

## License / 许可

© 2026 Tony Lin. See `LICENSE`.
