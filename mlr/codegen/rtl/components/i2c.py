# @brief i2c 组件 RTL 生成模块，负责输出适配器和实例连接代码。
# @date 2026-08-19
# @author hzguo

from __future__ import annotations

from pathlib import Path

from mlr.project import ComponentSpec, ProjectSpec, ServiceSpec, sanitize_identifier


I2C_SERVICE_NAMES = [
    "set_clk_div",
    "set_stretch_timeout",
    "set_dev_addr",
    "set_reg_addr",
    "set_length",
    "push_write_data",
    "start_write",
    "start_read",
    "pop_read_data",
    "get_status",
    "clear_status",
]


# @brief 读取整数 manifest 参数，支持带下划线的字符串。
def _int_param(component: ComponentSpec, key: str, default: int) -> int:
    raw = component.parameters.get(key, default)
    if isinstance(raw, str):
        raw = raw.replace("_", "")
    return int(raw)


# @brief 校验 i2c 组件是否包含固定服务集合。
def _require_i2c_services(component: ComponentSpec) -> dict[str, ServiceSpec]:
    services = {service.name: service for service in component.services}
    missing = [name for name in I2C_SERVICE_NAMES if name not in services]
    if missing:
        raise ValueError(
            f"i2c component {component.name} missing services: {', '.join(missing)}"
        )
    return services


# @brief 生成 I2C 服务适配器模块的 Verilog 源码行。
# @return I2C 适配器模块的 Verilog 源码行列表。
def emit_i2c_adapter() -> list[str]:
    repo_root = Path(__file__).resolve().parents[4]
    adapter_path = repo_root / "components" / "i2c" / "rtl" / "periphx_i2c_adapter.v"
    return adapter_path.read_text(encoding="utf-8").strip().splitlines()


# @brief 生成单个 i2c 组件实例与服务槽位连接的 Verilog 源码行。
# @param spec 规范化后的工程配置、组件和服务信息。
# @param component 当前 i2c 组件规格信息。
# @return 组件实例和服务槽位连接的 Verilog 源码行列表。
def emit_i2c_instance(spec: ProjectSpec, component: ComponentSpec) -> list[str]:
    del spec

    services = _require_i2c_services(component)
    port_map = component.pin_port_names
    if "i2c_scl" not in port_map:
        raise ValueError(f"i2c component {component.name} is missing i2c_scl pin mapping")
    if "i2c_sda" not in port_map:
        raise ValueError(f"i2c component {component.name} is missing i2c_sda pin mapping")

    clk_div = _int_param(component, "clk_div", 250)
    stretch_timeout = _int_param(component, "stretch_timeout", 1024)
    buffer_depth = _int_param(component, "buffer_depth", 16)
    if clk_div < 0:
        raise ValueError(f"{component.name}.clk_div must be non-negative")
    if stretch_timeout < 0:
        raise ValueError(f"{component.name}.stretch_timeout must be non-negative")
    if buffer_depth <= 0:
        raise ValueError(f"{component.name}.buffer_depth must be positive")

    inst_name = sanitize_identifier(component.name)
    svc_list = [services[name] for name in I2C_SERVICE_NAMES]

    lines = [f"    // {component.component_type} instance: {component.name}"]
    for service in svc_list:
        idx = service.service_id
        lines.extend(
            [
                f"    wire svc_{idx}_req_valid = slot_req_valid[{idx}];",
                f"    wire [3:0] svc_{idx}_req_msg_type = slot_req_msg_type[({idx}*4) +: 4];",
                f"    wire [31:0] svc_{idx}_req_payload = slot_req_payload[({idx}*32) +: 32];",
                f"    wire svc_{idx}_rsp_valid;",
                f"    wire [3:0] svc_{idx}_rsp_msg_type;",
                f"    wire [31:0] svc_{idx}_rsp_payload;",
                f"    assign slot_rsp_valid[{idx}] = svc_{idx}_rsp_valid;",
                f"    assign slot_rsp_msg_type[({idx}*4) +: 4] = svc_{idx}_rsp_msg_type;",
                f"    assign slot_rsp_payload[({idx}*32) +: 32] = svc_{idx}_rsp_payload;",
            ]
        )
    lines.append("")
    lines.extend(
        [
            "    periphx_i2c_adapter #(",
            f"        .DEFAULT_CLK_DIV({clk_div}),",
            f"        .DEFAULT_STRETCH_TIMEOUT({stretch_timeout}),",
            f"        .BUFFER_DEPTH({buffer_depth})",
            f"    ) u_{inst_name} (",
            "        .clk                       (clk),",
            "        .rst_n                     (rst_n),",
        ]
    )

    for service in svc_list:
        idx = service.service_id
        prefix = service.port_prefix
        lines.extend(
            [
                f"        .{prefix}_req_valid       (svc_{idx}_req_valid),",
                f"        .{prefix}_req_msg_type    (svc_{idx}_req_msg_type),",
                f"        .{prefix}_req_payload     (svc_{idx}_req_payload),",
                f"        .{prefix}_rsp_valid       (svc_{idx}_rsp_valid),",
                f"        .{prefix}_rsp_msg_type    (svc_{idx}_rsp_msg_type),",
                f"        .{prefix}_rsp_payload     (svc_{idx}_rsp_payload),",
            ]
        )

    lines.extend(
        [
            f"        .i2c_scl                 ({port_map['i2c_scl']}),",
            f"        .i2c_sda                 ({port_map['i2c_sda']})",
            "    );",
        ]
    )
    return lines


# @brief 返回 i2c 组件指定引脚的顶层方向。
# @param pin_name i2c 组件 interface 中的引脚名称。
# @return input、output 或 inout。
def i2c_pin_direction(pin_name: str) -> str:
    if pin_name in {"i2c_scl", "i2c_sda"}:
        return "inout"
    return "output"
