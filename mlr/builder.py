from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from mlr.codegen import generate_artifacts
from mlr.project import load_manifest, load_project_spec


PROJECT_NAME = "periphx_generated"


def build_workspace(workspace_dir: Path, run_quartus: bool = True) -> None:
    manifest_path = workspace_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    manifest = load_manifest(manifest_path)
    spec = load_project_spec(workspace_dir, manifest)

    repo_root = workspace_dir.parent
    output_root = repo_root / "tests" / "build" / "mlr"
    output_root.mkdir(parents=True, exist_ok=True)

    artifacts = generate_artifacts(spec, output_root)
    print(f"[OK] Generated RTL: {artifacts['rtl']}")
    print(f"[OK] Generated SDK: {artifacts['sdk_h']}")
    print(f"[OK] Service map: {artifacts['service_map']}")

    if not run_quartus:
        print("[INFO] Quartus step skipped by request.")
        return

    eda_path = spec.fpga.get("EDA_path")
    if not eda_path:
        print("[INFO] EDA_path is empty, bitstream build skipped.")
        return

    eda_exe = Path(str(eda_path))
    if not eda_exe.exists():
        print(f"[INFO] Quartus executable not found, bitstream build skipped: {eda_exe}")
        return

    quartus_dir = output_root / "quartus"
    quartus_dir.mkdir(parents=True, exist_ok=True)
    tcl_path = quartus_dir / "run_flow.tcl"
    _write_quartus_script(spec, artifacts["rtl"], tcl_path, quartus_dir)
    print("[INFO] Quartus compile started. This step can take several minutes.")
    _run_quartus(eda_exe, tcl_path, quartus_dir)


def run_altera_flow(workspace_dir: Path, manifest_data: dict, run_quartus: bool = True) -> None:
    """Compatibility wrapper for older entry points."""
    manifest_path = workspace_dir / "manifest.yaml"
    spec = load_project_spec(workspace_dir, manifest_data)

    repo_root = workspace_dir.parent
    output_root = repo_root / "tests" / "build" / "mlr"
    output_root.mkdir(parents=True, exist_ok=True)

    artifacts = generate_artifacts(spec, output_root)
    if not run_quartus:
        print("[INFO] Quartus step skipped by request.")
        return

    eda_path = spec.fpga.get("EDA_path")
    if not eda_path or not Path(str(eda_path)).exists():
        print("[INFO] Quartus executable not found, generation only.")
        return

    quartus_dir = output_root / "quartus"
    quartus_dir.mkdir(parents=True, exist_ok=True)
    tcl_path = quartus_dir / "run_flow.tcl"
    _write_quartus_script(spec, artifacts["rtl"], tcl_path, quartus_dir)
    _run_quartus(Path(str(eda_path)), tcl_path, quartus_dir)


def _write_quartus_script(spec, generated_rtl: Path, tcl_path: Path, quartus_dir: Path) -> None:
    repo_root = spec.workspace_dir.parent
    core_rtl_dir = repo_root / "components" / "core"
    sdc_path = quartus_dir / f"{PROJECT_NAME}.sdc"
    _write_quartus_sdc(spec, sdc_path)

    verilog_files = []
    for rtl_file in sorted(core_rtl_dir.glob("*.v")):
        verilog_files.append(rtl_file)
    for component in spec.components:
        rtl_dir = repo_root / "components" / component.component_type / "rtl"
        for rtl_file in sorted(rtl_dir.glob("*.v")):
            verilog_files.append(rtl_file)
    verilog_files.append(generated_rtl)

    tcl_lines = [
        "package require ::quartus::project",
        "package require ::quartus::flow",
        f"project_new {PROJECT_NAME} -overwrite",
        f"set_global_assignment -name FAMILY \"{spec.fpga.get('family', '')}\"",
        f"set_global_assignment -name DEVICE {spec.fpga.get('device', '')}",
        "set_global_assignment -name TOP_LEVEL_ENTITY periphx_top",
        "set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files",
        f"set_global_assignment -name SDC_FILE \"{sdc_path.resolve().as_posix()}\"",
        "set_global_assignment -name TIMEQUEST_REPORT_SCRIPT_INCLUDE_DEFAULT_ANALYSIS OFF",
    ]

    for verilog_file in verilog_files:
        tcl_lines.append(
            f"set_global_assignment -name VERILOG_FILE \"{verilog_file.resolve().as_posix()}\""
        )

    tcl_lines.extend(_emit_pin_assignments(spec))
    tcl_lines.extend(
        [
            "export_assignments",
            "if { [catch { execute_flow -compile } res] } {",
            "    project_close",
            "    exit 1",
            "} else {",
            "    project_close",
            "    exit 0",
            "}",
        ]
    )

    tcl_path.write_text("\n".join(tcl_lines) + "\n", encoding="utf-8")


def _write_quartus_sdc(spec, sdc_path: Path) -> None:
    clock_cfg = spec.config.get("clock", {}) or {}
    input_freq = clock_cfg.get("input_freq")

    try:
        freq_hz = float(input_freq)
    except (TypeError, ValueError):
        freq_hz = 50_000_000.0

    if freq_hz <= 0:
        freq_hz = 50_000_000.0

    period_ns = 1_000_000_000.0 / freq_hz

    sdc_lines = [
        "# Auto-generated by mlr.",
        f"create_clock -name sys_clk -period {period_ns:.3f} [get_ports {{clk}}]",
        f"create_clock -name spi_clk -period {period_ns:.3f} [get_ports {{spi_clk}}]",
        "set_clock_groups -asynchronous -group {sys_clk} -group {spi_clk}",
        "set_false_path -from [get_ports {rst_n}] -to [all_registers]",
    ]
    sdc_path.write_text("\n".join(sdc_lines) + "\n", encoding="utf-8")


def _emit_pin_assignments(spec) -> list[str]:
    lines: list[str] = []

    def add_pin(port: str, pin: str | None) -> None:
        if not pin:
            return
        lines.append(f"set_location_assignment {pin} -to {port}")
        lines.append(f"set_instance_assignment -name IO_STANDARD \"3.3-V LVCMOS\" -to {port}")

    add_pin("clk", spec.clock_pin)
    add_pin("rst_n", spec.rst_pin)
    add_pin("spi_clk", spec.spi_pins.get("spi_clk_pin"))
    add_pin("spi_cs_n", spec.spi_pins.get("spi_cs_pin"))
    add_pin("spi_mosi", spec.spi_pins.get("spi_mosi_pin"))
    add_pin("spi_miso", spec.spi_pins.get("spi_miso_pin"))

    for component in spec.components:
        for pin_name, port_name in component.pin_port_names.items():
            add_pin(port_name, component.pins.get(pin_name))

    return lines


def _run_quartus(eda_exe: Path, tcl_path: Path, quartus_dir: Path) -> None:
    process = subprocess.Popen(
        [str(eda_exe), "-t", str(tcl_path.name)],
        cwd=str(quartus_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="gbk",
        errors="ignore",
    )

    assert process.stdout is not None
    for line in process.stdout:
        sys.stdout.write(line)
    process.wait()

    if process.returncode != 0:
        print(f"[ERROR] Quartus compile failed with exit code {process.returncode}")
        return

    dist_dir = quartus_dir.parent / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    src_sof = quartus_dir / "output_files" / f"{PROJECT_NAME}.sof"
    if src_sof.exists():
        shutil.copy(src_sof, dist_dir / f"{PROJECT_NAME}.sof")
        print(f"[OK] Bitstream copied to {dist_dir / f'{PROJECT_NAME}.sof'}")

    for child_name in ("db", "incremental_db", "output_files"):
        child = quartus_dir / child_name
        if child.exists():
            shutil.rmtree(child)
