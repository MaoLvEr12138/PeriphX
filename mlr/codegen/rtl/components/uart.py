# @brief uart 组件 RTL 生成模块，负责输出适配器和实例连接代码。
# @date 2026-08-10
# @author hzguo

from __future__ import annotations

from textwrap import dedent

from mlr.project import ComponentSpec, ProjectSpec, ServiceSpec, sanitize_identifier


UART_SERVICE_NAMES = ["configure", "write_byte", "read_byte", "get_status"]
PARITY_CODES = {"none": 0, "odd": 1, "even": 2}


def _clock_hz(spec: ProjectSpec) -> int:
    clock_cfg = spec.config.get("clock", {}) or {}
    raw_freq = clock_cfg.get("input_freq", 50_000_000)
    if isinstance(raw_freq, str):
        raw_freq = raw_freq.replace("_", "")
    freq = int(raw_freq)
    if freq <= 0:
        raise ValueError("clock.input_freq must be positive for uart")
    return freq


def _int_param(component: ComponentSpec, key: str, default: int) -> int:
    raw = component.parameters.get(key, default)
    if isinstance(raw, str):
        raw = raw.replace("_", "")
    return int(raw)


def _parity_param(component: ComponentSpec) -> int:
    raw = str(component.parameters.get("parity", "none")).strip().lower()
    if raw not in PARITY_CODES:
        raise ValueError(f"{component.name}.parity must be one of none, odd, even")
    return PARITY_CODES[raw]


# @brief 根据 manifest 默认参数计算 UART packed config。
# @param spec 规范化后的工程配置。
# @param component 当前 uart 组件规格。
# @return packed config payload。
def uart_default_config_payload(spec: ProjectSpec, component: ComponentSpec) -> int:
    baudrate = _int_param(component, "baudrate", 115200)
    data_bits = _int_param(component, "data_bits", 8)
    stop_bits = _int_param(component, "stop_bits", 1)
    parity = _parity_param(component)
    clock_hz = _clock_hz(spec)

    if baudrate <= 0:
        raise ValueError(f"{component.name}.baudrate must be positive")
    if data_bits < 5 or data_bits > 8:
        raise ValueError(f"{component.name}.data_bits must be 5, 6, 7, or 8")
    if stop_bits not in {1, 2}:
        raise ValueError(f"{component.name}.stop_bits must be 1 or 2")

    baud_div = (clock_hz + (baudrate // 2)) // baudrate
    if baud_div <= 0 or baud_div > 0xFFFF:
        raise ValueError(
            f"{component.name}.baudrate produces unsupported baud_div {baud_div}"
        )

    payload = baud_div & 0xFFFF
    payload |= (data_bits - 5) << 16
    payload |= parity << 19
    payload |= (stop_bits - 1) << 21
    return payload


def _require_uart_services(component: ComponentSpec) -> dict[str, ServiceSpec]:
    services = {service.name: service for service in component.services}
    missing = [name for name in UART_SERVICE_NAMES if name not in services]
    if missing:
        raise ValueError(
            f"uart component {component.name} missing services: {', '.join(missing)}"
        )
    return services


# @brief 生成 UART 服务适配器模块的 Verilog 源码行。
# @return UART 适配器模块的 Verilog 源码行列表。
def emit_uart_adapter() -> list[str]:
    return dedent(
        """
        module periphx_uart_adapter
        #(
            parameter [31:0] DEFAULT_CONFIG = 32'h0003_01B2
        )
        (
            input  wire        clk,
            input  wire        rst_n,

            input  wire        configure_req_valid,
            input  wire [3:0]  configure_req_msg_type,
            input  wire [31:0] configure_req_payload,
            output reg         configure_rsp_valid,
            output reg  [3:0]  configure_rsp_msg_type,
            output reg  [31:0] configure_rsp_payload,

            input  wire        write_byte_req_valid,
            input  wire [3:0]  write_byte_req_msg_type,
            input  wire [31:0] write_byte_req_payload,
            output reg         write_byte_rsp_valid,
            output reg  [3:0]  write_byte_rsp_msg_type,
            output reg  [31:0] write_byte_rsp_payload,

            input  wire        read_byte_req_valid,
            input  wire [3:0]  read_byte_req_msg_type,
            input  wire [31:0] read_byte_req_payload,
            output reg         read_byte_rsp_valid,
            output reg  [3:0]  read_byte_rsp_msg_type,
            output reg  [31:0] read_byte_rsp_payload,

            input  wire        get_status_req_valid,
            input  wire [3:0]  get_status_req_msg_type,
            input  wire [31:0] get_status_req_payload,
            output reg         get_status_rsp_valid,
            output reg  [3:0]  get_status_rsp_msg_type,
            output reg  [31:0] get_status_rsp_payload,

            input  wire        uart_rxd,
            output wire        uart_txd
        );

        localparam [3:0] MSG_REQUEST = 4'h0;
        localparam [3:0] MSG_RESPONSE = 4'h1;
        localparam [3:0] MSG_ERROR = 4'h3;

        localparam [31:0] UART_ERR_BAD_CONFIG = 32'h0000_0010;
        localparam [31:0] UART_ERR_TX_FULL    = 32'h0000_0011;
        localparam [31:0] UART_ERR_RX_EMPTY   = 32'h0000_0012;
        localparam [31:0] UART_ERR_BUSY       = 32'h0000_0013;
        localparam [31:0] ERR_BAD_TYPE        = 32'h0000_0002;

        reg         cfg_valid;
        reg  [31:0] cfg_payload;
        wire        cfg_bad_config;
        wire        cfg_busy;
        reg         tx_write;
        reg  [7:0]  tx_write_data;
        wire        tx_full;
        wire        tx_empty;
        wire        tx_busy;
        reg         rx_read;
        wire [7:0]  rx_read_data;
        wire        rx_empty;
        wire        rx_full;
        wire [31:0] uart_status;
        wire [15:0] configure_baud_div;
        wire [2:0]  configure_data_bits_code;
        wire [1:0]  configure_parity;
        wire        configure_reserved_nonzero;
        wire        configure_data_bits_invalid;
        wire        configure_parity_invalid;
        wire        configure_bad_config;

        assign configure_baud_div = configure_req_payload[15:0];
        assign configure_data_bits_code = configure_req_payload[18:16];
        assign configure_parity = configure_req_payload[20:19];
        assign configure_reserved_nonzero = |configure_req_payload[31:22];
        assign configure_data_bits_invalid = (configure_data_bits_code > 3'd3);
        assign configure_parity_invalid = (configure_parity == 2'd3);
        assign configure_bad_config = (
            (configure_baud_div == 16'd0) ||
            configure_reserved_nonzero ||
            configure_data_bits_invalid ||
            configure_parity_invalid
        );

        uart_core #(
            .DEFAULT_CONFIG(DEFAULT_CONFIG)
        ) u_uart_core (
            .clk              (clk),
            .rst_n            (rst_n),
            .cfg_valid        (cfg_valid),
            .cfg_payload      (cfg_payload),
            .cfg_bad_config   (cfg_bad_config),
            .cfg_busy         (cfg_busy),
            .tx_write         (tx_write),
            .tx_write_data    (tx_write_data),
            .tx_full          (tx_full),
            .tx_empty         (tx_empty),
            .tx_busy          (tx_busy),
            .rx_read          (rx_read),
            .rx_read_data     (rx_read_data),
            .rx_empty         (rx_empty),
            .rx_full          (rx_full),
            .status           (uart_status),
            .uart_rxd         (uart_rxd),
            .uart_txd         (uart_txd)
        );

        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) begin
                configure_rsp_valid <= 1'b0;
                configure_rsp_msg_type <= 4'h0;
                configure_rsp_payload <= 32'd0;
                write_byte_rsp_valid <= 1'b0;
                write_byte_rsp_msg_type <= 4'h0;
                write_byte_rsp_payload <= 32'd0;
                read_byte_rsp_valid <= 1'b0;
                read_byte_rsp_msg_type <= 4'h0;
                read_byte_rsp_payload <= 32'd0;
                get_status_rsp_valid <= 1'b0;
                get_status_rsp_msg_type <= 4'h0;
                get_status_rsp_payload <= 32'd0;
                cfg_valid <= 1'b0;
                cfg_payload <= 32'd0;
                tx_write <= 1'b0;
                tx_write_data <= 8'd0;
                rx_read <= 1'b0;
            end else begin
                configure_rsp_valid <= 1'b0;
                configure_rsp_msg_type <= MSG_RESPONSE;
                configure_rsp_payload <= 32'd0;
                write_byte_rsp_valid <= 1'b0;
                write_byte_rsp_msg_type <= MSG_RESPONSE;
                write_byte_rsp_payload <= 32'd0;
                read_byte_rsp_valid <= 1'b0;
                read_byte_rsp_msg_type <= MSG_RESPONSE;
                read_byte_rsp_payload <= 32'd0;
                get_status_rsp_valid <= 1'b0;
                get_status_rsp_msg_type <= MSG_RESPONSE;
                get_status_rsp_payload <= 32'd0;
                cfg_valid <= 1'b0;
                cfg_payload <= 32'd0;
                tx_write <= 1'b0;
                tx_write_data <= 8'd0;
                rx_read <= 1'b0;

                if(configure_req_valid) begin
                    configure_rsp_valid <= 1'b1;
                    if(configure_req_msg_type != MSG_REQUEST) begin
                        configure_rsp_msg_type <= MSG_ERROR;
                        configure_rsp_payload <= ERR_BAD_TYPE;
                    end else if(tx_busy) begin
                        configure_rsp_msg_type <= MSG_ERROR;
                        configure_rsp_payload <= UART_ERR_BUSY;
                    end else if(configure_bad_config) begin
                        configure_rsp_msg_type <= MSG_ERROR;
                        configure_rsp_payload <= UART_ERR_BAD_CONFIG;
                    end else begin
                        cfg_valid <= 1'b1;
                        cfg_payload <= configure_req_payload;
                        configure_rsp_msg_type <= MSG_RESPONSE;
                        configure_rsp_payload <= configure_req_payload;
                    end
                end

                if(write_byte_req_valid) begin
                    write_byte_rsp_valid <= 1'b1;
                    if(write_byte_req_msg_type != MSG_REQUEST) begin
                        write_byte_rsp_msg_type <= MSG_ERROR;
                        write_byte_rsp_payload <= ERR_BAD_TYPE;
                    end else if(tx_full) begin
                        write_byte_rsp_msg_type <= MSG_ERROR;
                        write_byte_rsp_payload <= UART_ERR_TX_FULL;
                    end else begin
                        tx_write <= 1'b1;
                        tx_write_data <= write_byte_req_payload[7:0];
                        write_byte_rsp_msg_type <= MSG_RESPONSE;
                        write_byte_rsp_payload <= {24'd0, write_byte_req_payload[7:0]};
                    end
                end

                if(read_byte_req_valid) begin
                    read_byte_rsp_valid <= 1'b1;
                    if(read_byte_req_msg_type != MSG_REQUEST) begin
                        read_byte_rsp_msg_type <= MSG_ERROR;
                        read_byte_rsp_payload <= ERR_BAD_TYPE;
                    end else if(rx_empty) begin
                        read_byte_rsp_msg_type <= MSG_ERROR;
                        read_byte_rsp_payload <= UART_ERR_RX_EMPTY;
                    end else begin
                        rx_read <= 1'b1;
                        read_byte_rsp_msg_type <= MSG_RESPONSE;
                        read_byte_rsp_payload <= {24'd0, rx_read_data};
                    end
                end

                if(get_status_req_valid) begin
                    get_status_rsp_valid <= 1'b1;
                    if(get_status_req_msg_type != MSG_REQUEST) begin
                        get_status_rsp_msg_type <= MSG_ERROR;
                        get_status_rsp_payload <= ERR_BAD_TYPE;
                    end else begin
                        get_status_rsp_msg_type <= MSG_RESPONSE;
                        get_status_rsp_payload <= uart_status;
                    end
                end
            end
        end

        endmodule
        """
    ).strip().splitlines()


# @brief 生成单个 uart 组件实例与服务槽位连接的 Verilog 源码行。
# @param spec 规范化后的工程配置、组件和服务信息。
# @param component 当前 uart 组件规格信息。
# @return 组件实例和服务槽位连接的 Verilog 源码行列表。
def emit_uart_instance(spec: ProjectSpec, component: ComponentSpec) -> list[str]:
    services = _require_uart_services(component)
    port_map = component.pin_port_names
    if "rxd" not in port_map:
        raise ValueError(f"uart component {component.name} is missing rxd pin mapping")
    if "txd" not in port_map:
        raise ValueError(f"uart component {component.name} is missing txd pin mapping")

    default_config = uart_default_config_payload(spec, component)
    inst_name = sanitize_identifier(component.name)

    configure = services["configure"]
    write_byte = services["write_byte"]
    read_byte = services["read_byte"]
    get_status = services["get_status"]
    svc_list = [configure, write_byte, read_byte, get_status]

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
            "    periphx_uart_adapter #(",
            f"        .DEFAULT_CONFIG(32'h{default_config:08X})",
            f"    ) u_{inst_name} (",
            "        .clk                       (clk),",
            "        .rst_n                     (rst_n),",
            f"        .configure_req_valid       (svc_{configure.service_id}_req_valid),",
            f"        .configure_req_msg_type    (svc_{configure.service_id}_req_msg_type),",
            f"        .configure_req_payload     (svc_{configure.service_id}_req_payload),",
            f"        .configure_rsp_valid       (svc_{configure.service_id}_rsp_valid),",
            f"        .configure_rsp_msg_type    (svc_{configure.service_id}_rsp_msg_type),",
            f"        .configure_rsp_payload     (svc_{configure.service_id}_rsp_payload),",
            f"        .write_byte_req_valid      (svc_{write_byte.service_id}_req_valid),",
            f"        .write_byte_req_msg_type   (svc_{write_byte.service_id}_req_msg_type),",
            f"        .write_byte_req_payload    (svc_{write_byte.service_id}_req_payload),",
            f"        .write_byte_rsp_valid      (svc_{write_byte.service_id}_rsp_valid),",
            f"        .write_byte_rsp_msg_type   (svc_{write_byte.service_id}_rsp_msg_type),",
            f"        .write_byte_rsp_payload    (svc_{write_byte.service_id}_rsp_payload),",
            f"        .read_byte_req_valid       (svc_{read_byte.service_id}_req_valid),",
            f"        .read_byte_req_msg_type    (svc_{read_byte.service_id}_req_msg_type),",
            f"        .read_byte_req_payload     (svc_{read_byte.service_id}_req_payload),",
            f"        .read_byte_rsp_valid       (svc_{read_byte.service_id}_rsp_valid),",
            f"        .read_byte_rsp_msg_type    (svc_{read_byte.service_id}_rsp_msg_type),",
            f"        .read_byte_rsp_payload     (svc_{read_byte.service_id}_rsp_payload),",
            f"        .get_status_req_valid      (svc_{get_status.service_id}_req_valid),",
            f"        .get_status_req_msg_type   (svc_{get_status.service_id}_req_msg_type),",
            f"        .get_status_req_payload    (svc_{get_status.service_id}_req_payload),",
            f"        .get_status_rsp_valid      (svc_{get_status.service_id}_rsp_valid),",
            f"        .get_status_rsp_msg_type   (svc_{get_status.service_id}_rsp_msg_type),",
            f"        .get_status_rsp_payload    (svc_{get_status.service_id}_rsp_payload),",
            f"        .uart_rxd                  ({port_map['rxd']}),",
            f"        .uart_txd                  ({port_map['txd']})",
            "    );",
        ]
    )
    return lines


# @brief 判断 uart 组件的指定引脚是否为输出方向。
# @param pin_name uart 组件 interface 中的引脚名称。
# @return True 表示输出引脚，False 表示输入引脚。
def is_uart_output_pin(pin_name: str) -> bool:
    return pin_name == "txd"
