# @brief 构建编排入口，负责加载 manifest 并调度产物生成和厂商流程。
# @date 2026-07-28
# @author hzguo


from __future__ import annotations

from pathlib import Path

from mlr.codegen import generate_artifacts
from mlr.project import load_manifest, load_project_spec
from mlr.vendors.altera.quartus import run_legacy_quartus_flow, run_quartus_flow

# @brief 计算 mlr 构建产物的默认输出根目录。
# @param workspace_dir userSpace 工作目录路径。
# @return tests/build/mlr 输出根目录路径。
def _mlr_output_root(workspace_dir: Path) -> Path:
    repo_root = workspace_dir.parent
    return repo_root / "tests" / "build" / "mlr"

# @brief 从工作区 manifest 生成 PeriphX 产物，并按需执行 Quartus 流程。
# @param workspace_dir userSpace 工作目录路径。
# @param run_quartus 是否在生成文件后继续执行 Quartus 编译。
# @return None。
def build_workspace(workspace_dir: Path, run_quartus: bool = True) -> None:
    manifest_path = workspace_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    manifest = load_manifest(manifest_path)
    spec = load_project_spec(workspace_dir, manifest)

    output_root = _mlr_output_root(workspace_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    artifacts = generate_artifacts(spec, output_root)
    print(f"[OK] Generated RTL: {artifacts['rtl']}")
    print(f"[OK] Generated SDK: {artifacts['sdk_h']}")
    print(f"[OK] Service map: {artifacts['service_map']}")

    if not run_quartus:
        print("[INFO] Quartus step skipped by request.")
        return

    run_quartus_flow(spec, artifacts["rtl"], output_root)

# @brief 兼容旧入口的 Altera 构建流程封装。
# @param workspace_dir userSpace 工作目录路径。
# @param manifest_data 已解析的 manifest 数据。
# @param run_quartus 是否在生成文件后继续执行 Quartus 编译。
# @return None。
def run_altera_flow(workspace_dir: Path, manifest_data: dict, run_quartus: bool = True) -> None:
    spec = load_project_spec(workspace_dir, manifest_data)

    output_root = _mlr_output_root(workspace_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    artifacts = generate_artifacts(spec, output_root)
    if not run_quartus:
        print("[INFO] Quartus step skipped by request.")
        return

    run_legacy_quartus_flow(spec, artifacts["rtl"], output_root)
