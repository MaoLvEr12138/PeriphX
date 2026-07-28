# @brief pwm_led 组件 RTL 生成模块，负责输出适配器和实例连接代码。
# @date 2026-07-28
# @author hzguo


from __future__ import annotations

from textwrap import dedent

from mlr.project import ComponentSpec, ProjectSpec, sanitize_identifier

# @brief 生成 pwm_led 服务适配器模块的 Verilog 源码行。
# @return pwm_led 适配器模块的 Verilog 源码行列表。
def emit_pwm_led_adapter() -> list[str]:
    return dedent(
        """
        module periphx_pwm_led_adapter (
            input  wire        clk,
            input  wire        rst_n,

            input  wire        set_sys_cnt_prds_req_valid,
            input  wire [3:0]  set_sys_cnt_prds_req_msg_type,
            input  wire [31:0] set_sys_cnt_prds_req_payload,
            output reg         set_sys_cnt_prds_rsp_valid,
            output reg  [3:0]  set_sys_cnt_prds_rsp_msg_type,
            output reg  [31:0] set_sys_cnt_prds_rsp_payload,

            input  wire        set_sys_cnt_duty_req_valid,
            input  wire [3:0]  set_sys_cnt_duty_req_msg_type,
            input  wire [31:0] set_sys_cnt_duty_req_payload,
            output reg         set_sys_cnt_duty_rsp_valid,
            output reg  [3:0]  set_sys_cnt_duty_rsp_msg_type,
            output reg  [31:0] set_sys_cnt_duty_rsp_payload,

            output wire        led_pwm
        );

        localparam [3:0] MSG_REQUEST = 4'h0;
        localparam [3:0] MSG_RESPONSE = 4'h1;
        localparam [3:0] MSG_ERROR = 4'h3;

        reg [31:0] sys_cnt_prds_r;
        reg [31:0] sys_cnt_duty_r;

        pwm_led u_pwm_led (
            .clk         (clk),
            .rst_n       (rst_n),
            .sys_cnt_prds(sys_cnt_prds_r),
            .sys_cnt_duty(sys_cnt_duty_r),
            .led_pwm     (led_pwm)
        );

        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) begin
                sys_cnt_prds_r <= 32'd0;
                sys_cnt_duty_r <= 32'd0;

                set_sys_cnt_prds_rsp_valid <= 1'b0;
                set_sys_cnt_prds_rsp_msg_type <= 4'h0;
                set_sys_cnt_prds_rsp_payload <= 32'd0;

                set_sys_cnt_duty_rsp_valid <= 1'b0;
                set_sys_cnt_duty_rsp_msg_type <= 4'h0;
                set_sys_cnt_duty_rsp_payload <= 32'd0;
            end else begin
                set_sys_cnt_prds_rsp_valid <= 1'b0;
                set_sys_cnt_prds_rsp_msg_type <= MSG_RESPONSE;
                set_sys_cnt_prds_rsp_payload <= 32'd0;

                set_sys_cnt_duty_rsp_valid <= 1'b0;
                set_sys_cnt_duty_rsp_msg_type <= MSG_RESPONSE;
                set_sys_cnt_duty_rsp_payload <= 32'd0;

                if(set_sys_cnt_prds_req_valid) begin
                    if(set_sys_cnt_prds_req_msg_type == MSG_REQUEST) begin
                        sys_cnt_prds_r <= set_sys_cnt_prds_req_payload;
                        set_sys_cnt_prds_rsp_valid <= 1'b1;
                        set_sys_cnt_prds_rsp_msg_type <= MSG_RESPONSE;
                        set_sys_cnt_prds_rsp_payload <= set_sys_cnt_prds_req_payload;
                    end else begin
                        set_sys_cnt_prds_rsp_valid <= 1'b1;
                        set_sys_cnt_prds_rsp_msg_type <= MSG_ERROR;
                        set_sys_cnt_prds_rsp_payload <= 32'h0000_0002;
                    end
                end

                if(set_sys_cnt_duty_req_valid) begin
                    if(set_sys_cnt_duty_req_msg_type == MSG_REQUEST) begin
                        sys_cnt_duty_r <= set_sys_cnt_duty_req_payload;
                        set_sys_cnt_duty_rsp_valid <= 1'b1;
                        set_sys_cnt_duty_rsp_msg_type <= MSG_RESPONSE;
                        set_sys_cnt_duty_rsp_payload <= set_sys_cnt_duty_req_payload;
                    end else begin
                        set_sys_cnt_duty_rsp_valid <= 1'b1;
                        set_sys_cnt_duty_rsp_msg_type <= MSG_ERROR;
                        set_sys_cnt_duty_rsp_payload <= 32'h0000_0002;
                    end
                end
            end
        end

        endmodule
        """
    ).strip().splitlines()

# @brief 生成单个 pwm_led 组件实例与服务槽位连接的 Verilog 源码行。
# @param spec 规范化后的工程配置、组件和服务信息。
# @param component 当前 pwm_led 组件规格信息。
# @return 组件实例和服务槽位连接的 Verilog 源码行列表。
def emit_pwm_led_instance(spec: ProjectSpec, component: ComponentSpec) -> list[str]:
    if len(component.services) != 2:
        raise ValueError(
            f"pwm_led component {component.name} expects exactly 2 services, got {len(component.services)}"
        )

    svc0 = component.services[0]
    svc1 = component.services[1]
    port_map = component.pin_port_names
    if "led_pwm" not in port_map:
        raise ValueError(f"pwm_led component {component.name} is missing led_pwm pin mapping")

    idx0 = svc0.service_id
    idx1 = svc1.service_id
    inst_name = sanitize_identifier(component.name)

    return [
        f"    // {component.component_type} instance: {component.name}",
        f"    wire svc_{idx0}_req_valid = slot_req_valid[{idx0}];",
        f"    wire [3:0] svc_{idx0}_req_msg_type = slot_req_msg_type[({idx0}*4) +: 4];",
        f"    wire [31:0] svc_{idx0}_req_payload = slot_req_payload[({idx0}*32) +: 32];",
        f"    wire svc_{idx1}_req_valid = slot_req_valid[{idx1}];",
        f"    wire [3:0] svc_{idx1}_req_msg_type = slot_req_msg_type[({idx1}*4) +: 4];",
        f"    wire [31:0] svc_{idx1}_req_payload = slot_req_payload[({idx1}*32) +: 32];",
        f"    wire svc_{idx0}_rsp_valid;",
        f"    wire [3:0] svc_{idx0}_rsp_msg_type;",
        f"    wire [31:0] svc_{idx0}_rsp_payload;",
        f"    wire svc_{idx1}_rsp_valid;",
        f"    wire [3:0] svc_{idx1}_rsp_msg_type;",
        f"    wire [31:0] svc_{idx1}_rsp_payload;",
        "",
        f"    assign slot_rsp_valid[{idx0}] = svc_{idx0}_rsp_valid;",
        f"    assign slot_rsp_msg_type[({idx0}*4) +: 4] = svc_{idx0}_rsp_msg_type;",
        f"    assign slot_rsp_payload[({idx0}*32) +: 32] = svc_{idx0}_rsp_payload;",
        f"    assign slot_rsp_valid[{idx1}] = svc_{idx1}_rsp_valid;",
        f"    assign slot_rsp_msg_type[({idx1}*4) +: 4] = svc_{idx1}_rsp_msg_type;",
        f"    assign slot_rsp_payload[({idx1}*32) +: 32] = svc_{idx1}_rsp_payload;",
        "",
        f"    periphx_pwm_led_adapter u_{inst_name} (",
        "        .clk                      (clk),",
        "        .rst_n                    (rst_n),",
        f"        .set_sys_cnt_prds_req_valid(svc_{idx0}_req_valid),",
        f"        .set_sys_cnt_prds_req_msg_type(svc_{idx0}_req_msg_type),",
        f"        .set_sys_cnt_prds_req_payload(svc_{idx0}_req_payload),",
        f"        .set_sys_cnt_prds_rsp_valid(svc_{idx0}_rsp_valid),",
        f"        .set_sys_cnt_prds_rsp_msg_type(svc_{idx0}_rsp_msg_type),",
        f"        .set_sys_cnt_prds_rsp_payload(svc_{idx0}_rsp_payload),",
        f"        .set_sys_cnt_duty_req_valid(svc_{idx1}_req_valid),",
        f"        .set_sys_cnt_duty_req_msg_type(svc_{idx1}_req_msg_type),",
        f"        .set_sys_cnt_duty_req_payload(svc_{idx1}_req_payload),",
        f"        .set_sys_cnt_duty_rsp_valid(svc_{idx1}_rsp_valid),",
        f"        .set_sys_cnt_duty_rsp_msg_type(svc_{idx1}_rsp_msg_type),",
        f"        .set_sys_cnt_duty_rsp_payload(svc_{idx1}_rsp_payload),",
        f"        .led_pwm                  ({port_map['led_pwm']})",
        "    );",
    ]

# @brief 判断 pwm_led 组件的指定引脚是否为输出方向。
# @param pin_name pwm_led 组件 interface 中的引脚名称。
# @return True 表示输出引脚，False 表示输入引脚。
def is_pwm_led_output_pin(pin_name: str) -> bool:
    return pin_name == "led_pwm"
