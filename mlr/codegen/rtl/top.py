# @brief 顶层 RTL 生成模块，负责输出 periphx_top 及组件连接逻辑。
# @date 2026-07-28
# @author hzguo


from __future__ import annotations

from pathlib import Path

from mlr.codegen.rtl.components.pwm_led import (
    emit_pwm_led_adapter,
    emit_pwm_led_instance,
    is_pwm_led_output_pin,
)
from mlr.codegen.rtl.components.uart import (
    emit_uart_adapter,
    emit_uart_instance,
    is_uart_output_pin,
)
from mlr.project import ComponentSpec, ProjectSpec

# @brief 生成包含组件适配器和 periphx_top 的 RTL 文件。
# @param spec 规范化后的工程配置、组件和服务信息。
# @param path 顶层生成 RTL 的目标路径。
# @return 写入完成后的目标路径。
def write_generated_rtl(spec: ProjectSpec, path: Path) -> Path:
    unique_types = []
    seen_types = set()
    for component in spec.components:
        if component.component_type not in seen_types:
            seen_types.add(component.component_type)
            unique_types.append(component.component_type)

    lines: list[str] = []
    lines.append("// Auto-generated PeriphX RTL.")
    lines.append("// Generated from userSpace/manifest.yaml.")
    lines.append("")

    for component_type in unique_types:
        if component_type == "pwm_led":
            lines.extend(emit_pwm_led_adapter())
        elif component_type == "uart":
            lines.extend(emit_uart_adapter())
        else:
            raise NotImplementedError(
                f"component type {component_type!r} is not supported by the current generator"
            )
        lines.append("")

    lines.extend(emit_top_module(spec))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

# @brief 生成 periphx_top 模块的 Verilog 源码行。
# @param spec 规范化后的工程配置、组件和服务信息。
# @return periphx_top 模块的 Verilog 源码行列表。
def emit_top_module(spec: ProjectSpec) -> list[str]:
    lines: list[str] = []
    port_lines = [
        "    input  wire clk,",
        "    input  wire rst_n,",
        "    input  wire spi_clk,",
        "    input  wire spi_cs_n,",
        "    input  wire spi_mosi,",
        "    output wire spi_miso,",
    ]
    for component in spec.components:
        for pin_name, port_name in component.pin_port_names.items():
            direction = "output" if is_output_pin(component, pin_name) else "input"
            port_lines.append(f"    {direction} wire {port_name},")

    if port_lines:
        port_lines[-1] = port_lines[-1].rstrip(",")

    lines.append("module periphx_top (")
    lines.extend(port_lines)
    lines.append(");")
    lines.append("")
    lines.append("    localparam integer NUM_SLOTS = 256;")
    lines.append(f"    localparam integer TOTAL_SERVICES = {spec.total_services};")
    lines.append("")
    lines.append("    wire [NUM_SLOTS-1:0] slot_service_valid;")
    lines.append("    wire [NUM_SLOTS-1:0] slot_req_valid;")
    lines.append("    wire [NUM_SLOTS*4-1:0] slot_req_msg_type;")
    lines.append("    wire [NUM_SLOTS*32-1:0] slot_req_payload;")
    lines.append("    wire [NUM_SLOTS-1:0] slot_rsp_valid;")
    lines.append("    wire [NUM_SLOTS*4-1:0] slot_rsp_msg_type;")
    lines.append("    wire [NUM_SLOTS*32-1:0] slot_rsp_payload;")
    lines.append("    wire tx_frame_valid;")
    lines.append("    wire tx_frame_ready;")
    lines.append("    wire [7:0] tx_server_id;")
    lines.append("    wire [31:0] tx_payload;")
    lines.append("    wire [3:0] tx_msg_type;")
    lines.append("    wire rx_frame_valid;")
    lines.append("    wire rx_frame_error;")
    lines.append("    wire [7:0] rx_server_id;")
    lines.append("    wire [31:0] rx_payload;")
    lines.append("    wire [3:0] rx_msg_type;")
    lines.append("    wire [3:0] rx_crc4;")
    lines.append("    wire router_busy;")
    lines.append("    wire router_error;")
    lines.append("    wire dbg_req_fire;")
    lines.append("    wire [7:0] dbg_req_slot;")
    lines.append("    wire dbg_rsp_fire;")
    lines.append("    wire [7:0] dbg_rsp_slot;")
    lines.append("")
    lines.append("    genvar slot_i;")
    lines.append("    generate")
    lines.append("        for(slot_i = 0; slot_i < NUM_SLOTS; slot_i = slot_i + 1) begin : gen_slot_valid")
    lines.append("            assign slot_service_valid[slot_i] = (slot_i < TOTAL_SERVICES) ? 1'b1 : 1'b0;")
    lines.append("        end")
    lines.append("    endgenerate")
    lines.append("")
    lines.append("    protocol_parse u_protocol_parse (")
    lines.append("        .clk           (clk),")
    lines.append("        .rst_n         (rst_n),")
    lines.append("        .spi_clk       (spi_clk),")
    lines.append("        .spi_cs_n      (spi_cs_n),")
    lines.append("        .spi_mosi      (spi_mosi),")
    lines.append("        .spi_miso      (spi_miso),")
    lines.append("        .cs_active     (),")
    lines.append("        .cs_start      (),")
    lines.append("        .cs_end        (),")
    lines.append("        .tx_frame_valid(tx_frame_valid),")
    lines.append("        .tx_frame_ready(tx_frame_ready),")
    lines.append("        .tx_server_id  (tx_server_id),")
    lines.append("        .tx_payload    (tx_payload),")
    lines.append("        .tx_msg_type   (tx_msg_type),")
    lines.append("        .rx_frame_valid(rx_frame_valid),")
    lines.append("        .rx_frame_error(rx_frame_error),")
    lines.append("        .rx_server_id  (rx_server_id),")
    lines.append("        .rx_payload    (rx_payload),")
    lines.append("        .rx_msg_type   (rx_msg_type),")
    lines.append("        .rx_crc4       (rx_crc4)")
    lines.append("    );")
    lines.append("")
    lines.append("    data_router #(.NUM_SLOTS(NUM_SLOTS)) u_data_router (")
    lines.append("        .clk              (clk),")
    lines.append("        .rst_n            (rst_n),")
    lines.append("        .slot_service_valid(slot_service_valid),")
    lines.append("        .req_valid        (rx_frame_valid),")
    lines.append("        .req_ready        (),")
    lines.append("        .req_service_id   (rx_server_id),")
    lines.append("        .req_msg_type     (rx_msg_type),")
    lines.append("        .req_payload      (rx_payload),")
    lines.append("        .tx_frame_valid   (tx_frame_valid),")
    lines.append("        .tx_frame_ready   (tx_frame_ready),")
    lines.append("        .tx_server_id     (tx_server_id),")
    lines.append("        .tx_payload       (tx_payload),")
    lines.append("        .tx_msg_type      (tx_msg_type),")
    lines.append("        .slot_req_valid   (slot_req_valid),")
    lines.append("        .slot_req_msg_type(slot_req_msg_type),")
    lines.append("        .slot_req_payload (slot_req_payload),")
    lines.append("        .slot_rsp_valid   (slot_rsp_valid),")
    lines.append("        .slot_rsp_msg_type(slot_rsp_msg_type),")
    lines.append("        .slot_rsp_payload (slot_rsp_payload),")
    lines.append("        .router_busy      (router_busy),")
    lines.append("        .router_error     (router_error),")
    lines.append("        .dbg_req_fire     (dbg_req_fire),")
    lines.append("        .dbg_req_slot     (dbg_req_slot),")
    lines.append("        .dbg_rsp_fire     (dbg_rsp_fire),")
    lines.append("        .dbg_rsp_slot     (dbg_rsp_slot)")
    lines.append("    );")
    lines.append("")
    lines.append("    generate")
    lines.append("        for(slot_i = 0; slot_i < NUM_SLOTS; slot_i = slot_i + 1) begin : gen_rsp_default")
    lines.append("            if(slot_i >= TOTAL_SERVICES) begin")
    lines.append("                assign slot_rsp_valid[slot_i] = 1'b0;")
    lines.append("                assign slot_rsp_msg_type[(slot_i*4) +: 4] = 4'h0;")
    lines.append("                assign slot_rsp_payload[(slot_i*32) +: 32] = 32'h0000_0000;")
    lines.append("            end")
    lines.append("        end")
    lines.append("    endgenerate")
    lines.append("")

    for component in spec.components:
        if component.component_type == "pwm_led":
            lines.extend(emit_pwm_led_instance(spec, component))
        elif component.component_type == "uart":
            lines.extend(emit_uart_instance(spec, component))
        else:
            raise NotImplementedError(
                f"component type {component.component_type!r} is not supported by the current generator"
            )
        lines.append("")

    lines.append("endmodule")
    return lines

# @brief 判断指定组件引脚在顶层端口中是否为输出方向。
# @param component 组件规格信息。
# @param pin_name 组件 interface 中的引脚名称。
# @return True 表示输出引脚，False 表示输入引脚。
def is_output_pin(component: ComponentSpec, pin_name: str) -> bool:
    if component.component_type == "pwm_led":
        return is_pwm_led_output_pin(pin_name)
    if component.component_type == "uart":
        return is_uart_output_pin(pin_name)
    return True
