# @brief 产物生成编排模块，负责组织 RTL、SDK 和元数据输出。
# @date 2026-07-28
# @author hzguo


from __future__ import annotations

from pathlib import Path

from mlr.codegen.meta import write_service_map, write_summary
from mlr.codegen.rtl.top import write_generated_rtl
from mlr.codegen.sdk import write_sdk_header, write_sdk_source
from mlr.project import ProjectSpec

# @brief 生成当前工程需要的 RTL、SDK 和元数据产物。
# @param spec 规范化后的工程配置、组件和服务信息。
# @param output_root 产物输出根目录。
# @return 产物名称到输出文件路径的映射。
def generate_artifacts(spec: ProjectSpec, output_root: Path) -> dict[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)

    rtl_dir = output_root / "rtl"
    sdk_dir = output_root / "sdk"
    meta_dir = output_root / "meta"
    build_dir = output_root / "quartus"

    rtl_dir.mkdir(parents=True, exist_ok=True)
    sdk_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    artifact_map: dict[str, Path] = {}
    artifact_map["service_map"] = write_service_map(spec, meta_dir / "service_map.json")
    artifact_map["sdk_h"] = write_sdk_header(spec, sdk_dir / "periphx_sdk.h")
    artifact_map["sdk_c"] = write_sdk_source(spec, sdk_dir / "periphx_sdk.c")
    artifact_map["rtl"] = write_generated_rtl(spec, rtl_dir / "periphx_generated.v")
    artifact_map["summary"] = write_summary(spec, meta_dir / "build_summary.json")
    return artifact_map
