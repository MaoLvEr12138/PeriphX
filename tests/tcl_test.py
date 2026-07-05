import os
import subprocess
import sys
import shutil

# ===================================================================
# 1. 模拟用户的 Manifest 配置 (后续可直接改成读取 JSON 或 YAML 文件)
# ===================================================================
manifest = {
    "project_name": "periphx_uart",
    "top_module": "uart_top",
    "device_info": {
        "family": "Cyclone IV E",
        "device": "EP4CE6E22C8"
    },
    # 核心 Verilog 文件列表
    "source_files": [
        "../components/uart/rtl/uart_top.v",
        "../components/uart/rtl/uart_tx.v",
        "../components/uart/rtl/uart_rx.v"
    ],
    # 用户引脚配置
    "pin_assignments": {
        "clk":   {"location": "PIN_24",  "io_standard": "3.3-V LVCMOS"},
        "rst_n": {"location": "PIN_25",  "io_standard": "3.3-V LVCMOS"},
        "txd":   {"location": "PIN_143", "io_standard": "3.3-V LVCMOS"},
        "rxd":   {"location": "PIN_144", "io_standard": "3.3-V LVCMOS"}
    }
}

# ===================================================================
# 2. 自动化构建核心逻辑
# ===================================================================
def build_fpga_project(project_dir, prj_manifest):
    name = prj_manifest["project_name"]
    top = prj_manifest["top_module"]
    dev = prj_manifest["device_info"]
    
    # 你的 Quartus 13.0.1 绝对路径
    quartus_sh = r"D:\Quarters13.0.1\quartus\bin64\quartus_sh.exe"
    
    print("====================================================")
    print(f" [PeriphX] 开始自动化构建流程: {name}")
    print("====================================================")

    # A. 动态组装 Tcl 脚本字符串
    tcl_commands = f"""
package require ::quartus::project
package require ::quartus::flow

# 强制新建工程，覆盖旧工程，保持环境纯净
project_new {name} -overwrite

# 配置芯片基本信息
set_global_assignment -name FAMILY "{dev['family']}"
set_global_assignment -name DEVICE {dev['device']}
set_global_assignment -name TOP_LEVEL_ENTITY {top}
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files
"""

    # 动态把源码文件塞进 Tcl
    for src in prj_manifest["source_files"]:
        tcl_commands += f"set_global_assignment -name VERILOG_FILE {src}\n"

    # 动态绑定引脚和电平标准
    for pin, info in prj_manifest["pin_assignments"].items():
        tcl_commands += f"set_location_assignment {info['location']} -to {pin}\n"
        tcl_commands += f"set_instance_assignment -name IO_STANDARD \"{info['io_standard']}\" -to {pin}\n"

    # 写入全编译控制流命令
    tcl_commands += f"""
export_assignments

puts "--> INFO: 正在拉起 Quartus 13.0 工作流，启动全量编译综合..."
if {{ [catch {{ execute_flow -compile }} res] }} {{
    puts "--> ERROR: 编译失败，捕获错误: $res"
    project_close
    exit 1
}} else {{
    puts "--> SUCCESS: 固件已成功产出！"
    project_close
    exit 0
}}
"""

    # B. 将 Tcl 落地为物理文件
    tcl_file_path = os.path.join(project_dir, "run_flow.tcl")
    with open(tcl_file_path, "w", encoding="utf-8") as f:
        f.write(tcl_commands)

    # C. 用 subprocess 拉起 quartus_sh.exe 执行该 Tcl
    cmd = [quartus_sh, "-t", "run_flow.tcl"]
    
    process = subprocess.Popen(
        cmd,
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='gbk', # Windows 下 Quartus 报警告或错误时通常是 GBK 编码
        errors='ignore'
    )

    # 实时流式捕获 Quartus 的编译日志，显示在 Python 控制台
    for line in process.stdout:
        sys.stdout.write(line)

    process.wait()

    # D. 编译结果检查与制品处理
    if process.returncode == 0:
        print("\n====================================================")
        print(" [√] 编译成功！正在提取 Bitstream 并为您清理战局...")
        print("====================================================")
        
        # 建立最终制品的发布交付目录
        dist_dir = os.path.join(project_dir, "dist")
        os.makedirs(dist_dir, exist_ok=True)
        
        # 寻找生成的源 .sof 文件
        target_sof = os.path.join(project_dir, "output_files", f"{name}.sof")
        final_sof = os.path.join(dist_dir, f"{name}.sof")
        
        if os.path.exists(target_sof):
            shutil.copy(target_sof, final_sof)
            print(f"🎉 核心固件已提取成功！-> {final_sof}")
            
            # 【完美清场】删除所有恶心的临时工程文件，实现用户零感知
            clean_house(project_dir, name)
            return True
    else:
        print(f"\n[X] 编译失败，Quartus 异常退出，错误码: {process.returncode}")
        return False

def clean_house(project_dir, prj_name):
    """
    静默删除所有 Quartus 的工程配置文件和中间缓存文件夹
    """
    # 需要删除的垃圾文件夹
    garbage_dirs = ["db", "incremental_db", "output_files"]
    # 需要删除的垃圾单文件
    garbage_files = [
        "run_flow.tcl", 
        f"{prj_name}.qpf", 
        f"{prj_name}.qsf", 
        f"{prj_name}.qws"
    ]
    
    for d in garbage_dirs:
        path = os.path.join(project_dir, d)
        if os.path.exists(path):
            shutil.rmtree(path)
            
    for f in garbage_files:
        path = os.path.join(project_dir, f)
        if os.path.exists(path):
            os.remove(path)
            
    print("🧹 缓存清空完毕！.qpf / .qsf 及中间数据库已全部静默擦除。")

# ===================================================================
# 3. 脚本执行入口
# ===================================================================
if __name__ == "__main__":
    # 当前脚本所在目录（确保你的三个 .v 文件也在这个目录下）
    current_workspace = os.path.dirname(os.path.abspath(__file__))
    
    build_fpga_project(current_workspace, manifest)