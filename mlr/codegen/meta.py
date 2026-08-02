# @brief 构建元数据生成模块，负责输出服务映射和构建摘要。
# @date 2026-07-28
# @author hzguo


from __future__ import annotations

from pathlib import Path
import json

from mlr.project import ProjectSpec

# @brief 将服务 ID、组件和接口信息写入 service_map.json。
# @param spec 规范化后的工程配置、组件和服务信息。
# @param path service_map.json 的目标路径。
# @return 写入完成后的目标路径。
def write_service_map(spec: ProjectSpec, path: Path) -> Path:
    services = []
    for service in spec.services:
        services.append(
            {
                "service_id": service.service_id,
                "component_type": service.component_type,
                "component_name": service.component_name,
                "service_name": service.name,
                "access": service.access,
                "type": service.data_type,
                "width": service.width,
                "code_hint": service.code_hint,
            }
        )

    data = {
        "manifest": str(spec.manifest_path),
        "total_services": spec.total_services,
        "services": services,
    }
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    return path

# @brief 将工作区、组件和服务摘要写入 build_summary.json。
# @param spec 规范化后的工程配置、组件和服务信息。
# @param path build_summary.json 的目标路径。
# @return 写入完成后的目标路径。
def write_summary(spec: ProjectSpec, path: Path) -> Path:
    data = {
        "workspace_dir": str(spec.workspace_dir),
        "manifest_path": str(spec.manifest_path),
        "total_components": len(spec.components),
        "total_services": spec.total_services,
        "components": [
            {
                "component_type": comp.component_type,
                "component_name": comp.name,
                "services": [service.name for service in comp.services],
                "pins": comp.pins,
            }
            for comp in spec.components
        ],
    }
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    return path
