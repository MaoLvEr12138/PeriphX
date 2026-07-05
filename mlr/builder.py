import os
import sys
import subprocess
import shutil
from pathlib import Path


def run_altera_flow(workspace_dir: Path, manifest_data: dict):
    """
    Altera 平台全自动编译主控核心
    """
    # 1. 从manifest解析参数
    project_name = "periphx_generated"
    eda_path, fpga_info, global_pins, components = _parse_manifest(manifest_data)
    
    # 2. 生成 Tcl 构建任务单
    tcl_path = workspace_dir / "run_flow.tcl"
    _generate_tcl_script(tcl_path, project_name, fpga_info, global_pins, components, workspace_dir)
    
    # 3. 拉起 EDA 工具链子进程
    cmd = [eda_path, "-t", "run_flow.tcl"]
    process = subprocess.Popen(
        cmd,
        cwd=str(workspace_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='gbk',
        errors='ignore'
    )
    
    # 流式输出 Quartus 原始编译日志
    for line in process.stdout:
        sys.stdout.write(line)
    process.wait()
    
    # 4. 产物交付与垃圾现场清洗
    if process.returncode == 0:
        _deliver_artifacts(workspace_dir, project_name)
        _clean_workspace(workspace_dir, project_name)
    else:
        print(f"\n[Error] FPGA Compilation failed with exit code: {process.returncode}")


def _parse_manifest(manifest_data: dict):
    """
    解析块：从原始字典提取清晰的硬件配置子集
    """
    config = manifest_data.get("config", {})
    fpga_cfg = config.get("fpga", {})
    
    eda_path = fpga_cfg.get("EDA_path")
    
    fpga_info = {
        "family": fpga_cfg.get("family"),
        "device": fpga_cfg.get("device")
    }
    
    global_pins = {
        "clk": config.get("clock", {}).get("input_pin"),
        "rst_n": config.get("rst", {}).get("input_pin")
    }
    
    components = manifest_data.get("components", [])
    
    return eda_path, fpga_info, global_pins, components


def _generate_tcl_script(tcl_path: Path, prj_name: str, fpga: dict, global_pins: dict, components: list, workspace_dir: Path):
    """
    构建块：编排纯粹的 Tcl 语法网表及引脚映射清单
    """
    tcl_lines = [
        "package require ::quartus::project",
        "package require ::quartus::flow",
        f"project_new {prj_name} -overwrite",
        f"set_global_assignment -name FAMILY \"{fpga['family']}\"",
        f"set_global_assignment -name DEVICE {fpga['device']}",
        "set_global_assignment -name TOP_LEVEL_ENTITY uart_top",
        "set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files"
    ]
    
    # 注入基础全局时钟与复位引脚
    if global_pins["clk"]:
        tcl_lines.append(f"set_location_assignment {global_pins['clk']} -to sys_clk")
        tcl_lines.append(f"set_instance_assignment -name IO_STANDARD \"3.3-V LVCMOS\" -to sys_clk")
        
    if global_pins["rst_n"]:
        tcl_lines.append(f"set_location_assignment {global_pins['rst_n']} -to sys_rst_n")
        tcl_lines.append(f"set_instance_assignment -name IO_STANDARD \"3.3-V LVCMOS\" -to sys_rst_n")
        
    # 遍历外设组件，定位 Verilog 源码及引脚
    repo_root = workspace_dir.parent
    
    for comp in components:
        comp_type = comp.get("type")
        pins = comp.get("pins", {})
        
        # 搜寻对应组件下的所有 .v 源文件
        rtl_dir = repo_root / "components" / comp_type / "rtl"
        if rtl_dir.exists():
            for v_file in rtl_dir.glob("*.v"):
                clean_path = str(v_file.resolve()).replace('\\', '/')
                tcl_lines.append(f"set_global_assignment -name VERILOG_FILE \"{clean_path}\"")
                
        # 精准对接硬核端口 uart_txd / uart_rxd
        if comp_type == "uart":
            if "tx" in pins:
                tcl_lines.append(f"set_location_assignment {pins['tx']} -to uart_txd")
                tcl_lines.append(f"set_instance_assignment -name IO_STANDARD \"3.3-V LVCMOS\" -to uart_txd")
            if "rx" in pins:
                tcl_lines.append(f"set_location_assignment {pins['rx']} -to uart_rxd")
                tcl_lines.append(f"set_instance_assignment -name IO_STANDARD \"3.3-V LVCMOS\" -to uart_rxd")
                
    # 写入执行流控制
    tcl_lines.extend([
        "export_assignments",
        "if { [catch { execute_flow -compile } res] } {",
        "    project_close",
        "    exit 1",
        "} else {",
        "    project_close",
        "    exit 0",
        "}"
    ])
    
    with open(tcl_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tcl_lines))


def _deliver_artifacts(workspace_dir: Path, prj_name: str):
    """
    交付块：将生成的编译原件 sof 移送到用户可见的 dist 目录
    """
    dist_dir = workspace_dir / "dist"
    dist_dir.mkdir(exist_ok=True)
    
    src_sof = workspace_dir / "output_files" / f"{prj_name}.sof"
    dest_sof = dist_dir / f"{prj_name}.sof"
    
    if src_sof.exists():
        shutil.copy(src_sof, dest_sof)
        print(f"\n[Success] Artifact delivered to: {dest_sof}")


def _clean_workspace(workspace_dir: Path, prj_name: str):
    """
    清洗块：斩断中间垃圾目录和衍生配置文件
    """
    garbage_dirs = ["db", "incremental_db", "output_files"]
    garbage_files = ["run_flow.tcl", f"{prj_name}.qpf", f"{prj_name}.qsf", f"{prj_name}.qws"]
    
    for d in garbage_dirs:
        path = workspace_dir / d
        if path.exists():
            shutil.rmtree(path)
            
    for f in garbage_files:
        path = workspace_dir / f
        if path.exists():
            os.remove(path)