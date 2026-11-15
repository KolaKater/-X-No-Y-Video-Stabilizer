# -*- coding: utf-8 -*-
"""
vid_stablizer.py - 只做左右(X轴)防抖
方案一: FFmpeg vidstab (解析 .trf, 把 dy 和旋转清零, 只保留 dx)
方案二: Python + OpenCV (只跟踪 dx, 只补偿 dx)
相对路径: ffmpeg.exe / ffprobe.exe 在同目录下的 bin\ 文件夹, 即 D:\3D\Easy3D\ffmpeg\bin\ffmpeg.exe
"""
import os, re, subprocess, shutil, json, sys
from pathlib import Path

# PyInstaller 打包后: _MEIPASS = 解压目录 (读资源), EXE 所在目录 = 可写目录 (日志/.trf)
if getattr(sys, "frozen", False):
    HERE = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))  # 资源: bin\ffmpeg.exe
    APP_DIR = Path(sys.executable).resolve().parent  # 可写: 日志 / .trf
else:
    HERE = Path(__file__).resolve().parent
    APP_DIR = HERE
def _find_exe(name):
    # 优先: D:\3D\Easy3D\ffmpeg\bin\ffmpeg.exe (你的实际位置)
    # 其次: 同目录 / bin / 系统 PATH
    candidates = [HERE / "bin" / name, HERE / name, Path("bin") / name]
    for c in candidates:
        if c.exists():
            return str(c.resolve())
    return name  # 回退到系统 PATH
FFMPEG = _find_exe("ffmpeg.exe")
FFPROBE = _find_exe("ffprobe.exe")

# ---------- Debug Log: vid_stablizer_debug.log (same folder as this file) ----------
import logging, datetime
LOG_PATH = APP_DIR / "vid_stablizer_debug.log"
_logger = logging.getLogger("vid_stablizer")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False
if not _logger.handlers:
    try:
        _fh = logging.FileHandler(str(LOG_PATH), encoding="utf-8", mode="w")  # 每次启动清空, 不追加, 日志不会越写越大
        _fh.setLevel(logging.DEBUG)
        _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        _logger.addHandler(_fh)
        _ch = logging.StreamHandler()
        _ch.setLevel(logging.INFO)
        _ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        _logger.addHandler(_ch)
    except Exception as e:
        print(f"cannot setup debug log: {e}")
def debug_log(msg, level="info"):
    # 统一入口: GUI 和本模块都调这个, 既写文件也打印
    try:
        getattr(_logger, level, _logger.info)(str(msg))
    except Exception:
        print(str(msg))
    return str(msg)
def log_startup():
    debug_log("="*60)
    debug_log(f"START vid_stablizer | HERE={HERE} | FFMPEG={FFMPEG} | FFPROBE={FFPROBE} | LOG={LOG_PATH}")
    debug_log(f"Python={__import__('sys').version.split()[0]} | Platform={__import__('platform').platform()}")
log_startup()

# ---------- 通用工具: 隐藏 ffmpeg/ffprobe 的 CMD 窗口 ----------
import sys as _sys
if _sys.platform == "win32":
    _NO_WINDOW = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    try:
        _si = subprocess.STARTUPINFO(); _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; _si.wShowWindow = 0
        _NO_WINDOW["startupinfo"] = _si
    except Exception: pass
else:
    _NO_WINDOW = {}
def run(cmd, cwd=None):
    cmd_str = " ".join(str(c) for c in cmd)
    debug_log(f"RUN: {cmd_str}")
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="ignore", **_NO_WINDOW)
    if r.returncode != 0:
        debug_log(f"FAILED rc={r.returncode}: {cmd_str}", "error")
        debug_log(f"OUTPUT tail: {r.stdout[-4000:]}", "error")
        raise RuntimeError(f"命令失败: {cmd[0]}")
    debug_log(f"OK rc=0: {cmd[0]}")
    return r.stdout

def get_video_info(video_path):
    """返回 dict: width,height,fps,has_audio,duration"""
    cmd = [FFPROBE, "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(video_path)]
    debug_log(f"get_video_info: {video_path}")
    out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore", **_NO_WINDOW).stdout
    data = json.loads(out) if out.strip() else {}
    vs = next((s for s in data.get("streams", []) if s.get("codec_type")=="video"), {})
    has_audio = any(s.get("codec_type")=="audio" for s in data.get("streams", []))
    w, h = int(vs.get("width", 0)), int(vs.get("height", 0))
    fps_str = vs.get("r_frame_rate") or vs.get("avg_frame_rate") or "30/1"
    try:
        num, den = fps_str.split("/"); fps = float(num)/float(den) if float(den)!=0 else 30.0
    except: fps = 30.0
    debug_log(f"get_video_info result: {w}x{h} fps={fps} has_audio={has_audio}")
    return {"width": w, "height": h, "fps": fps, "has_audio": has_audio,
            "duration": float(data.get("format", {}).get("duration", 0) or 0)}

def parse_fps_label(label):
    m = {"23.976fps": "24000/1001", "24fps": "24", "25fps": "25", "29.97fps": "30000/1001",
         "30fps": "30", "50fps": "50", "60fps": "60", "120fps": "120"}
    return m.get(label, "30")

def fps_float(label):
    m = {"23.976fps": 23.976, "24fps": 24, "25fps": 25, "29.97fps": 29.97,
         "30fps": 30, "50fps": 50, "60fps": 60, "120fps": 120}
    return m.get(label, 30.0)

def crop_w_for_x_only(width):
    """只做左右防抖时, 只需要裁左右, 上下不动.
       1920 -> 1910 (左右各裁 5), 保持高度不变, 保证偶数."""
    new_w = width - 10
    if new_w % 2 == 1: new_w -= 1
    return new_w

def output_video_name(video_path: Path, new_w, new_h, method="ffmpeg"):
    # 文件名后缀加上 _ffmpeg / _opencv, 尺寸用实际输出尺寸 (原尺寸模式就是原尺寸)
    return video_path.with_name(f"{video_path.stem}_{new_w}x{new_h}_{method}_stablized.mp4")

def output_frames_dir(frames_dir: Path):
    return frames_dir.parent / f"{frames_dir.name}_stablized"

# ---------- 帧序列重命名 ----------
IMAGE_EXTS = {".jpg",".jpeg",".png",".bmp",".tif",".tiff",".webp",".gif",".heic",".heif",".avif",".jxl",".ppm",".pgm",".tga"}
def list_frames(folder: Path):
    files = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    return sorted(files)

def rename_frames(folder, prefix="frame", start=1, pad=4):
    """把帧统一重命名为 frame_0001.jpg 这种格式, 返回新文件列表. 不改变顺序."""
    folder = Path(folder)
    files = list_frames(folder)
    # 先临时重命名避免冲突
    tmp = []
    for i, f in enumerate(files):
        t = folder / f"__tmp_{i:06d}{f.suffix.lower()}"
        f.rename(t); tmp.append(t)
    out = []
    for i, t in enumerate(tmp):
        new = folder / f"{prefix}_{start+i:0{pad}d}.jpg"
        # 统一转 jpg 需要重编码, 如果原图就是 jpg 直接改名即可
        if t.suffix.lower() in (".jpg", ".jpeg"):
            t.rename(new)
        else:
            import cv2
            img = cv2.imread(str(t))
            cv2.imwrite(str(new), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            t.unlink()
        out.append(new)
    return out

# ---------- 方案二: OpenCV 只做 X ----------
def stabilize_frames_opencv_x_only(input_dir, output_dir, smoothing_radius=30, crop_each_side=5, quality=95, on_progress=None, keep_original_size=False, ref="global", warp="off"):
    """ref: global=整帧算 dx | foreground=只用中央区特征点 (人/主体为准) | background=只用边缘区特征点 (背景为准)
    warp: off=整帧一个 dx 平移 | mesh_light/medium/heavy=局部网格 warp, 只做 X, 三级强度/网格密度:
      light: 4x3 网格, 网格权重 0.35 | medium: 6x4 网格, 权重 0.65 | heavy: 8x6 网格, 权重 1.0
    网格 warp 仍以水平为主: 只 warp X, Y 不动."""
    import cv2, numpy as np
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = list_frames(input_dir)
    if not files: raise FileNotFoundError(f"没有找到帧: {input_dir}")
    debug_log(f"stabilize_frames_opencv_x_only: in={input_dir} out={output_dir} frames={len(files)} smoothing={smoothing_radius} crop={crop_each_side} keep_original={keep_original_size} ref={ref} warp={warp}")
    first = cv2.imread(str(files[0]))
    if first is None: raise RuntimeError(f"无法读取第一帧: {files[0]}")
    h, w = first.shape[:2]; new_w = w - crop_each_side*2
    # --- 区域掩码: 前景=中央, 背景=边缘 ---
    def _in_region(x, y):
        if ref == "foreground": return (0.22*w <= x <= 0.78*w) and (0.15*h <= y <= 0.85*h)
        if ref == "background": return (x < 0.20*w) or (x > 0.80*w) or (y < 0.15*h) or (y > 0.85*h)
        return True
    # --- 网格配置 ---
    _mesh = {"off": (0, 0, 0.0), "mesh_light": (4, 3, 0.35), "mesh_medium": (6, 4, 0.65), "mesh_heavy": (8, 6, 1.0)}.get(warp, (0, 0, 0.0))
    _cols, _rows, _mesh_w = _mesh; _use_mesh = _cols > 0
    # --- 1. 逐对帧估计 dx: 全局 + 每网格 ---
    transforms = []; cell_series = []  # 每帧一个 (rows,cols) 的 dx
    prev_gray = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
    prev_pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=400, qualityLevel=0.01, minDistance=25)
    for i in range(1, len(files)):
        curr = cv2.imread(str(files[i]))
        if curr is None:
            debug_log(f"stabilize_frames_opencv: skip unreadable frame {files[i].name}", "warning")
            transforms.append(0.0)
            if _use_mesh: cell_series.append(np.zeros((_rows, _cols)))
            continue
        curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
        if prev_pts is None or len(prev_pts) == 0:
            transforms.append(0.0)
            if _use_mesh: cell_series.append(np.zeros((_rows, _cols)))
            prev_gray = curr_gray; prev_pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=400, qualityLevel=0.01, minDistance=25); continue
        curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, prev_pts, None)
        idx = np.where(status.flatten() == 1)[0] if status is not None else []
        gdx = 0.0; cell = np.zeros((_rows, _cols)) if _use_mesh else None
        if len(idx) >= 5:
            # 按 ref 过滤特征点, 不够 10 个则回退整帧 (避免某区域没纹理时崩)
            keep = [k for k in idx if _in_region(prev_pts[k, 0, 0], prev_pts[k, 0, 1])]
            if len(keep) < 10: keep = list(idx)
            dxs = curr_pts[keep, 0, 0] - prev_pts[keep, 0, 0]
            gdx = float(np.median(dxs))
            if _use_mesh:
                for r in range(_rows):
                    for c in range(_cols):
                        pts_in = [k for k in keep if int(prev_pts[k,0,1]/(h/_rows)) == r and int(prev_pts[k,0,0]/(w/_cols)) == c]
                        if len(pts_in) >= 3:
                            cell[r, c] = float(np.median(curr_pts[pts_in,0,0] - prev_pts[pts_in,0,0]))
                        else: cell[r, c] = gdx
        transforms.append(gdx)
        if _use_mesh: cell_series.append(cell)
        prev_gray = curr_gray; prev_pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=400, qualityLevel=0.01, minDistance=25)
        if on_progress: on_progress(i * 0.5, len(files))  # 估计阶段占前 50%
        if i % 100 == 0: debug_log(f"stabilize_frames_opencv: estimating {i}/{len(files)}")
    transforms = np.array(transforms, dtype=np.float64)
    # --- 2. 累积轨迹 + 平滑 (全局和每网格都做) ---
    def _smooth_series(arr):
        # 前缀和滑动平均 O(n), 原来每点都 mean 一段窗口是 O(n*window), smoothing 大 + 网格多时卡死
        arr = np.asarray(arr, dtype=np.float64); n = len(arr)
        if n == 0: return arr.copy()
        cs = np.concatenate([[0.0], np.cumsum(arr)])
        idx = np.arange(n); s = np.maximum(0, idx - smoothing_radius); e = np.minimum(n, idx + smoothing_radius + 1)
        return (cs[e] - cs[s]) / (e - s)
    traj = np.cumsum(transforms); diff = _smooth_series(traj) - traj; diff = np.concatenate([[0.0], diff])
    cell_diff = None
    if _use_mesh:
        cell_arr = np.stack(cell_series)  # (N-1, rows, cols)
        cell_traj = np.cumsum(cell_arr, axis=0); cell_sm = np.stack([_smooth_series(cell_traj[:, r, c]) for r in range(_rows) for c in range(_cols)], axis=1).reshape(len(cell_traj), _rows, _cols) if False else None
        # 逐网格平滑 (上面一行只是占位, 这里重算, 保证维度正确)
        cell_sm = np.zeros_like(cell_traj)
        for r in range(_rows):
            for c in range(_cols): cell_sm[:, r, c] = _smooth_series(cell_traj[:, r, c])
        cell_diff = np.concatenate([np.zeros((1, _rows, _cols)), cell_sm - cell_traj], axis=0)  # (N, rows, cols)
        # 网格补偿与全局补偿混合: light 0.35 网格 + 0.65 全局, 依此类推
        cell_diff = cell_diff * _mesh_w + diff[:, None, None] * (1.0 - _mesh_w)
        # 空间过渡放大: 先对每帧的网格 dx 做高斯平滑, 消除相邻网格的突变, 避免小范围大变形
        for _i in range(len(cell_diff)):
            cell_diff[_i] = cv2.GaussianBlur(cell_diff[_i].astype(np.float32), (0, 0), sigmaX=1.2, sigmaY=1.2)
    # --- 3. 逐帧补偿 ---
    _prev_img = None
    for i, f in enumerate(files):
        img = cv2.imread(str(f))
        if img is None:
            debug_log(f"stabilize_frames_opencv: unreadable frame {f.name}, reuse previous", "warning"); img = _prev_img if _prev_img is not None else first.copy()
        _prev_img = img
        if _use_mesh:
            # 网格 dx 场放大到全图, 再用大 sigma 高斯平滑做宽过渡 (过渡宽度约 1 个网格以上), remap 只做 X, Y 不动
            field = cv2.resize(cell_diff[i].astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
            field = cv2.GaussianBlur(field, (0, 0), sigmaX=8, sigmaY=8)  # 小 sigma 收尾, 大 sigma 巨型卷积是卡死主因
            xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
            warped = cv2.remap(img, xs - field, ys, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        else:
            M = np.float32([[1, 0, diff[i]], [0, 1, 0]])
            warped = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        cropped = warped[:, crop_each_side:w-crop_each_side]
        if keep_original_size:
            blurred = cv2.GaussianBlur(warped, (0, 0), sigmaX=25, sigmaY=25); out_img = blurred.copy(); out_img[:, crop_each_side:crop_each_side+new_w] = cropped
        else: out_img = cropped
        cv2.imwrite(str(output_dir / f"{f.stem}_opencv_stablized.jpg"), out_img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if on_progress: on_progress(len(files)*0.5 + (i+1)*0.5, len(files))  # 补偿阶段占后 50%
    return {"width": (w if keep_original_size else new_w), "height": h, "count": len(files)}


def _safe_trf(tag="x"):
    """关键修复: -vf 里的 : 和空格会被 FFmpeg 当成滤镜分隔符解析.
    所以 .trf 绝不能用 'E:\\AI video\\...\\__xxx.trf' 这种带盘符/空格的完整路径.
    改成放程序目录 D:\\3D\\Easy3D\\ffmpeg\\ 下的纯英文无空格文件名, 滤镜里只传文件名,
    并用 cwd=HERE 让 ffmpeg 在程序目录找它."""
    import re as _re
    safe = _re.sub(r"[^A-Za-z0-9_]+", "_", str(tag))[:40] or "x"
    path = APP_DIR / f"__vidstab_{safe}.trf"
    return path, path.name

# ---------- 方案一: FFmpeg vidstab, 只保留 X ----------
def _vidstab_filter(trf_name, smoothing, new_w, h, crop_each_side, keep_original_size, out_w):
    """裁切模式专用 (-vf): transform -> crop. 原尺寸多路图绝不能进 -vf, 见 _vidstab_filter_complex."""
    base_f = f"vidstabtransform=input={trf_name}:zoom=1:optzoom=0:crop=0:maxangle=0:smoothing={smoothing}"
    return f"{base_f},crop={new_w}:{h}:{crop_each_side}:0,format=yuv420p"

def _vidstab_filter_complex(trf_name, smoothing, new_w, h, crop_each_side):
    """原尺寸模式专用, 配合 -filter_complex + -map [vout]:
    [0:v] -> transform -> split: 一路 crop 清晰中间, 一路 gblur 模糊整帧做底, overlay 贴回中间."""
    return (f"[0:v]vidstabtransform=input={trf_name}:zoom=1:optzoom=0:crop=0:maxangle=0:smoothing={smoothing},"
            f"split=2[sharp][bg];"
            f"[sharp]crop={new_w}:{h}:{crop_each_side}:0[sharp_c];"
            f"[bg]gblur=sigma=25[bg_blur];"
            f"[bg_blur][sharp_c]overlay={crop_each_side}:0,format=yuv420p[vout]")


def _filter_trf_x_only(trf_path):
    """只做 X: .trf 只有 ASCII 格式才能改, 二进制格式绝不碰.
    ASCII 格式: Frame N (List M [(LM x y fx fy size contrast match), ...])
    只把每个 (LM x y ...) 里的 y 置 0, 保留 x, 其它字节/换行原样不动.
    之前把文件按空格切开置 0 会破坏 (LM ...) 和二进制结构 -> Cannot parse localmotion! + 崩溃 rc=3221225477."""
    import re as _re
    data = Path(trf_path).read_bytes()
    # 二进制: 以 TRF 开头, 或含 NUL 字节 -> 不改, 直接返回 False, 让 vidstab 按原样跑 (不会崩)
    if data[:3] == b"TRF" or b"\x00" in data[:4096]:
        debug_log(f"_filter_trf_x_only: binary .trf, skipped (not modified) {trf_path}", "warning")
        return False
    try:
        text = data.decode("utf-8", errors="strict")
    except Exception:
        debug_log(f"_filter_trf_x_only: not utf-8 text, skipped {trf_path}", "warning")
        return False
    if "Frame" not in text or "(LM" not in text:
        debug_log(f"_filter_trf_x_only: unknown format, skipped {trf_path}", "warning")
        return False
    # (LM 3 -2 32 ...) -> (LM 3 0 32 ...): 只替换 y, 保留 x 和其余字段
    new_text, n = _re.subn(r"(\(LM\s+[^\s)]+\s+)[^\s)]+", r"\g<1>0", text)
    if n == 0:
        debug_log(f"_filter_trf_x_only: no (LM ...) found, skipped {trf_path}", "warning")
        return False
    # 原样写回: 不改换行, 不改编码, 不做 split/join
    Path(trf_path).write_bytes(new_text.encode("utf-8"))
    debug_log(f"_filter_trf_x_only: ASCII .trf, y=0 applied to {n} local motions in {trf_path}")
    return True

def stabilize_frames_ffmpeg_x_only(input_dir, output_dir, smoothing=30, crop_each_side=5, quality=95, fps_label="30fps", save_as="frames", keep_original_size=False):
    """save_as: 'frames' 或 'mp4'"""
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    files = list_frames(input_dir)
    if not files: raise FileNotFoundError(f"没有找到帧: {input_dir}")
    debug_log(f"stabilize_frames_ffmpeg_x_only: in={input_dir} out={output_dir} frames={len(files)} smoothing={smoothing} fps={fps_label} save_as={save_as} keep_original={keep_original_size}")
    import cv2
    h, w = cv2.imread(str(files[0])).shape[:2]
    new_w = w - crop_each_side*2
    fps_str = parse_fps_label(fps_label)
    tmp_in = input_dir.parent / f"__tmp_in_{input_dir.name}"
    if tmp_in.exists(): shutil.rmtree(tmp_in)
    tmp_in.mkdir(parents=True)
    try:
        for i, f in enumerate(files, start=1):
            img = cv2.imread(str(f))
            cv2.imwrite(str(tmp_in / f"frame_{i:04d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        trf, trf_name = _safe_trf(f"frames_{input_dir.name}")
        run([FFMPEG, "-y", "-framerate", fps_str, "-i", str(tmp_in / "frame_%04d.jpg"),
             "-vf", f"vidstabdetect=shakiness=10:accuracy=15:result={trf_name}", "-f", "null", "-"], cwd=HERE)
        _filter_trf_x_only(trf)
        vf = _vidstab_filter(trf_name, smoothing, new_w, h, crop_each_side, keep_original_size, w)
        tmp_out = input_dir.parent / f"__tmp_out_{input_dir.name}"
        if tmp_out.exists(): shutil.rmtree(tmp_out)
        tmp_out.mkdir(parents=True)
        if save_as == "frames":
            output_dir.mkdir(parents=True, exist_ok=True)
            if keep_original_size:
                # 原尺寸多路图必须走 -filter_complex, 不能走 -vf (见 _vidstab_filter_complex)
                fc = _vidstab_filter_complex(trf_name, smoothing, new_w, h, crop_each_side).replace(",format=yuv420p[vout]", "[vout]")
                run([FFMPEG, "-y", "-framerate", fps_str, "-i", str(tmp_in / "frame_%04d.jpg"),
                     "-filter_complex", fc, "-map", "[vout]", "-q:v", "2", str(tmp_out / "frame_%04d.jpg")], cwd=HERE)
            else:
                vf_frames = vf.replace(",format=yuv420p", "")
                run([FFMPEG, "-y", "-framerate", fps_str, "-i", str(tmp_in / "frame_%04d.jpg"),
                     "-vf", vf_frames, "-q:v", "2", str(tmp_out / "frame_%04d.jpg")], cwd=HERE)
            outs = sorted(tmp_out.glob("*.jpg"))
            for i, o in enumerate(outs, start=1):
                orig = files[i-1].stem
                img = cv2.imread(str(o))
                cv2.imwrite(str(output_dir / f"{orig}_ffmpeg_stablized.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, quality])
            shutil.rmtree(tmp_out)
        else:
            mp4_path = input_dir.parent / f"{input_dir.name}_{fps_label}_ffmpeg_stablized.mp4"
            if keep_original_size:
                fc = _vidstab_filter_complex(trf_name, smoothing, new_w, h, crop_each_side)
                run([FFMPEG, "-y", "-framerate", fps_str, "-i", str(tmp_in / "frame_%04d.jpg"),
                     "-filter_complex", fc, "-map", "[vout]", "-c:v", "libx265", "-crf", "18", "-preset", "medium", "-tag:v", "hvc1", str(mp4_path)], cwd=HERE)
            else:
                run([FFMPEG, "-y", "-framerate", fps_str, "-i", str(tmp_in / "frame_%04d.jpg"),
                     "-vf", vf, "-c:v", "libx265", "-crf", "18", "-preset", "medium", "-tag:v", "hvc1", str(mp4_path)], cwd=HERE)
            return {"width": (w if keep_original_size else new_w), "height": h, "mp4": str(mp4_path)}
    finally:
        if tmp_in.exists(): shutil.rmtree(tmp_in, ignore_errors=True)
        try:
            _tf, _ = _safe_trf(f"frames_{input_dir.name}")
            if _tf.exists(): _tf.unlink()
        except Exception: pass
    return {"width": (w if keep_original_size else new_w), "height": h, "count": len(files)}

# ---------- 视频文件 ----------
def stabilize_video_file(video_path, method="ffmpeg", smoothing=30, crop_each_side=5, on_progress=None, keep_original_size=False, ref="global", warp="off"):
    video_path = Path(video_path)
    debug_log(f"stabilize_video_file: {video_path} method={method} smoothing={smoothing} crop={crop_each_side} keep_original={keep_original_size}")
    info = get_video_info(video_path)
    w, h = info["width"], info["height"]
    new_w = crop_w_for_x_only(w)
    out_w = w if keep_original_size else new_w
    out_path = output_video_name(video_path, out_w, h, method=method)
    fps_str = str(info["fps"])
    if method == "ffmpeg":
        trf, trf_name = _safe_trf(video_path.stem)
        run([FFMPEG, "-y", "-i", str(video_path),
             "-vf", f"vidstabdetect=shakiness=10:accuracy=15:result={trf_name}", "-f", "null", "-"], cwd=HERE)
        if on_progress: on_progress(50, 100)  # FFmpeg: 检测完成 50%
        _filter_trf_x_only(trf)
        # 注意: 有声/无声都要处理, 有音频则 -c:a copy, 无音频则不加音频参数
        # 原尺寸模式带 ; 的多路滤镜图必须走 -filter_complex + -map [vout], 绝不能走 -vf
        if keep_original_size:
            cmd = [FFMPEG, "-y", "-i", str(video_path),
                   "-filter_complex", _vidstab_filter_complex(trf_name, smoothing, new_w, h, crop_each_side),
                   "-map", "[vout]"]
            if info["has_audio"]:
                cmd += ["-map", "0:a:0", "-c:a", "copy"]
            cmd += ["-c:v", "libx265", "-crf", "18", "-preset", "medium", "-tag:v", "hvc1", str(out_path)]
        else:
            cmd = [FFMPEG, "-y", "-i", str(video_path),
                   "-vf", _vidstab_filter(trf_name, smoothing, new_w, h, crop_each_side, keep_original_size, w),
                   "-c:v", "libx265", "-crf", "18", "-preset", "medium", "-tag:v", "hvc1"]
            if info["has_audio"]:
                cmd += ["-c:a", "copy"]
            cmd += [str(out_path)]
        run(cmd, cwd=HERE)
        if on_progress: on_progress(100, 100)  # FFmpeg: 转换完成 100%
        if trf.exists(): trf.unlink()
    else:
        # OpenCV 方案: 先抽帧 -> 稳定 -> 再合成 (用 ffmpeg 合成, 保留音频)
        tmp_frames = video_path.parent / f"__frames_{video_path.stem}"
        tmp_stable = video_path.parent / f"__stable_{video_path.stem}"
        for d in (tmp_frames, tmp_stable):
            if d.exists(): shutil.rmtree(d)
            d.mkdir(parents=True)
        try:
            run([FFMPEG, "-y", "-i", str(video_path), "-q:v", "2", str(tmp_frames / "frame_%04d.jpg")])
            if on_progress: on_progress(10, 100)  # OpenCV: 抽帧完成 10%
            # 稳定内部进度是 0~100, 映射到 10%~90%, 避免进度往回跳
            def _prog_mapped(cur, tot):
                if on_progress: on_progress(10 + (cur / tot) * 80, 100)
            stabilize_frames_opencv_x_only(tmp_frames, tmp_stable, smoothing_radius=smoothing, crop_each_side=crop_each_side, on_progress=_prog_mapped, keep_original_size=keep_original_size, ref=ref, warp=warp)
            if on_progress: on_progress(90, 100)  # OpenCV: 稳定完成 90%, 接下来合成
            # 合成: 视频用稳定后的帧, 音频用原视频
            # Gyan 版 FFmpeg 不支持 glob, 且稳定后帧名是 *_opencv_stablized.jpg:
            # 先把稳定帧统一重命名为 frame_%04d.jpg 顺序名, 再用顺序名合成
            _stable_sorted = sorted(tmp_stable.glob("*.jpg"))
            for _idx, _sf in enumerate(_stable_sorted, start=1):
                _target = tmp_stable / f"frame_{_idx:04d}.jpg"
                if _sf.resolve() != _target.resolve():
                    if _target.exists(): _target.unlink()
                    _sf.rename(_target)
            cmd = [FFMPEG, "-y", "-framerate", fps_str, "-i", str(tmp_stable / "frame_%04d.jpg"),
                   "-i", str(video_path), "-map", "0:v:0"]
            if info["has_audio"]:
                cmd += ["-map", "1:a:0", "-c:a", "copy"]
            cmd += ["-c:v", "libx265", "-crf", "18", "-preset", "medium", "-tag:v", "hvc1",
                    "-shortest", str(out_path)]
            run(cmd)
            if on_progress: on_progress(100, 100)  # OpenCV: 合成完成 100%
        finally:
            shutil.rmtree(tmp_frames, ignore_errors=True); shutil.rmtree(tmp_stable, ignore_errors=True)
    debug_log(f"stabilize_video_file DONE: {out_path}")
    return str(out_path)

if __name__ == "__main__":
    import sys
    print("vid_stablizer - 只做左右防抖. 请用 stablizer_gui.py 启动界面, 或 import 调用函数.")
