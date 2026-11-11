#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片元数据清理
==============

手机拍的照片普遍带 EXIF，里面可能有：
  - GPS 坐标（精确到门牌号）
  - 设备型号、序列号
  - 拍摄时间、甚至编辑软件的修改记录

这些都属于不该随图片一起公开的私密信息。上传时统一重编码一遍，
只保留像素与必要的色彩信息（ICC），丢掉 EXIF / XMP / 注释等。

动图（GIF / 动态 WEBP）逐帧重写，避免只留第一帧。
"""

import io
from typing import Optional, Tuple

# 重编码时各格式的参数
_JPEG_QUALITY = 95          # 高一点，避免二次压缩损失可见
_WEBP_QUALITY = 92
_PNG_COMPRESS = 6


def _frames_of(img):
    """展开所有帧（静态图返回单帧）"""
    from PIL import ImageSequence

    frames = []
    durations = []
    for frame in ImageSequence.Iterator(img):
        frames.append(frame.convert('RGBA'))
        durations.append(frame.info.get('duration', 100))
    return frames, durations


def strip_metadata(raw: bytes) -> Tuple[Optional[bytes], str]:
    """去掉图片里的私密元数据

    Returns:
        (new_bytes, message)
        new_bytes 为 None 表示处理失败，调用方应拒绝这次上传
        （宁可让用户重试，也不能把带 GPS 的原图存下来）
    """
    from PIL import Image

    try:
        with Image.open(io.BytesIO(raw)) as img:
            fmt = (img.format or '').upper()
            animated = getattr(img, 'is_animated', False) and getattr(img, 'n_frames', 1) > 1

            # 保留 ICC 色彩配置（不是隐私信息，丢了会偏色）
            icc = img.info.get('icc_profile')

            out = io.BytesIO()

            if animated:
                frames, durations = _frames_of(img)
                if not frames:
                    return None, '动图解析失败'

                first, rest = frames[0], frames[1:]
                params = {
                    'save_all': True,
                    'append_images': rest,
                    'duration': durations,
                    'loop': img.info.get('loop', 0),
                    'disposal': 2,
                }
                if fmt == 'GIF':
                    # GIF 只支持调色板，转回来才能保持体积
                    first = first.convert('P', palette=Image.ADAPTIVE)
                    rest = [f.convert('P', palette=Image.ADAPTIVE) for f in rest]
                    params['append_images'] = rest
                    first.save(out, format='GIF', **params)
                elif fmt == 'WEBP':
                    first.save(out, format='WEBP', quality=_WEBP_QUALITY, **params)
                else:
                    # 其它动图格式（如 APNG）按静止处理
                    return _save_static(img, fmt, icc)
            else:
                return _save_static(img, fmt, icc)

            data = out.getvalue()
            if not data:
                return None, '重编码结果为空'
            return data, f'已清理元数据（{fmt}）'

    except Exception as e:
        print(f'[ERROR] 清理图片元数据失败: {str(e)}')
        return None, f'图片元数据处理失败: {str(e)}'


def _save_static(img, fmt: str, icc) -> Tuple[Optional[bytes], str]:
    """静态图重编码：只写像素，不传 exif / pnginfo"""
    from PIL import Image

    out = io.BytesIO()
    save_kwargs = {}

    if fmt == 'JPEG':
        target = img.convert('RGB') if img.mode not in ('RGB', 'L') else img
        save_kwargs.update(quality=_JPEG_QUALITY, optimize=True, progressive=True)
    elif fmt == 'PNG':
        target = img.convert('RGBA') if img.mode in ('P', 'LA', 'RGBA') else img.convert('RGB')
        save_kwargs.update(optimize=True, compress_level=_PNG_COMPRESS)
    elif fmt == 'WEBP':
        target = img.convert('RGBA') if img.mode in ('P', 'LA', 'RGBA') else img.convert('RGB')
        save_kwargs.update(quality=_WEBP_QUALITY, method=4)
    elif fmt == 'GIF':
        target = img.convert('P', palette=Image.ADAPTIVE)
    else:
        # 不认识的格式：保持原样（调用方已用扩展名过滤过）
        return None, f'暂不支持的格式: {fmt}'

    if icc:
        save_kwargs['icc_profile'] = icc

    target.save(out, format=fmt, **save_kwargs)

    data = out.getvalue()
    if not data:
        return None, '重编码结果为空'
    return data, f'已清理元数据（{fmt}）'
