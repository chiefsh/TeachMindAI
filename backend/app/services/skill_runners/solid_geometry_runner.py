#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""立体几何 skill runner（子进程入口）。

用法：
    python3 solid_geometry_runner.py '<spec_json>' <out_html_path>

spec_json 至少含 problem_type，例如：
    {"problem_type": "line_plane_angle", "body": "pyramid", "base_edge": 2, "height": 1}
    {"problem_type": "line_plane_angle", "body": "cube"}
    {"problem_type": "volume", "lx": 3, "ly": 4, "lz": 5}

进程隔离运行，避免与其它 skill 的同名模块（geometry_kernel 等）冲突。
"""
import json
import sys
from pathlib import Path

# backend/app/services/skill_runners/solid_geometry_runner.py -> parents[3] = backend
SKILL_DIR = Path(__file__).resolve().parents[3] / "skills" / "edu-solid-geometry"
SCRIPTS_DIR = SKILL_DIR / "scripts"


def _load_generate():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import generate  # noqa: E402
    return generate


def _int(spec: dict, key: str, default: int) -> int:
    try:
        v = int(spec.get(key, default))
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


def build(spec: dict):
    gen = _load_generate()
    ptype = spec.get("problem_type")

    if ptype == "line_plane_angle":
        body = str(spec.get("body", "pyramid")).lower()
        if body == "cube":
            return gen.build_cube_data()
        base_edge = _int(spec, "base_edge", 2)
        height = _int(spec, "height", 1)
        return gen.build_data(base_edge=base_edge, height=height)

    if ptype == "volume":
        lx = _int(spec, "lx", 3)
        ly = _int(spec, "ly", 4)
        lz = _int(spec, "lz", 5)
        return gen.build_box_volume_data(lx, ly, lz)

    if ptype == "skew_lines":
        return gen.build_cube_skew_lines_data(_int(spec, "edge", 1))

    if ptype == "dihedral":
        return gen.build_tetra_dihedral_data()

    if ptype == "point_plane_distance":
        return gen.build_cube_point_plane_distance_data(_int(spec, "edge", 1))

    raise ValueError(f"不支持的 problem_type: {ptype}")


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: solid_geometry_runner.py <spec_json> <out_html>", file=sys.stderr)
        return 2
    try:
        spec = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"spec JSON 解析失败: {e}", file=sys.stderr)
        return 2
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)

    gen = _load_generate()
    data = build(spec)
    # 自检：最终步骤须包含计算所得答案（与答案卡同源）
    answer = data.get("_answer")
    if answer is not None:
        assert answer in data["steps"][-1]["content"], "最终步骤未包含计算所得答案"
        data.pop("_answer", None)
    gen.render_html(data, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
