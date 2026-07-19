"""Code generation for the PeriphX RTL, SDK, and build metadata."""

from __future__ import annotations

from pathlib import Path
import json
from textwrap import dedent

from mlr.project import ComponentSpec, ProjectSpec, sanitize_identifier


FRAME_LEN = 6
TURNAROUND_LEN = 3
TURNAROUND_BYTE = 0xFF
REQUEST_MSG_TYPE = 0x0
RESPONSE_MSG_TYPE = 0x1
EVENT_MSG_TYPE = 0x2
ERROR_MSG_TYPE = 0x3


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
    artifact_map["service_map"] = _write_service_map(spec, meta_dir / "service_map.json")
    artifact_map["sdk_h"] = _write_sdk_header(spec, sdk_dir / "periphx_sdk.h")
    artifact_map["sdk_c"] = _write_sdk_source(spec, sdk_dir / "periphx_sdk.c")
    artifact_map["rtl"] = _write_generated_rtl(spec, rtl_dir / "periphx_generated.v")
    artifact_map["summary"] = _write_summary(spec, meta_dir / "build_summary.json")
    return artifact_map


def _write_service_map(spec: ProjectSpec, path: Path) -> Path:
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


def _write_summary(spec: ProjectSpec, path: Path) -> Path:
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


def _write_sdk_header(spec: ProjectSpec, path: Path) -> Path:
    lines: list[str] = []
    lines.append("#ifndef PERIPHX_SDK_H")
    lines.append("#define PERIPHX_SDK_H")
    lines.append("")
    lines.append("#include <stdbool.h>")
    lines.append("#include <stddef.h>")
    lines.append("#include <stdint.h>")
    lines.append("")
    lines.append(f"#define PERIPHX_FRAME_LEN {FRAME_LEN}u")
    lines.append(f"#define PERIPHX_TURNAROUND_LEN {TURNAROUND_LEN}u")
    lines.append("#define PERIPHX_TRANSACTION_LEN (PERIPHX_FRAME_LEN + PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN)")
    lines.append(f"#define PERIPHX_MSG_REQUEST {REQUEST_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_RESPONSE {RESPONSE_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_EVENT {EVENT_MSG_TYPE:#x}u")
    lines.append(f"#define PERIPHX_MSG_ERROR {ERROR_MSG_TYPE:#x}u")
    lines.append("")
    lines.append("/*")
    lines.append(" * PeriphX transport baseline:")
    lines.append(" * The current FPGA bridge keeps a short byte-alignment window between the")
    lines.append(" * request and response halves of a transaction. The SDK therefore keeps")
    lines.append(" * CS low across a request window, three alignment bytes, and a readback")
    lines.append(" * window in a single SPI transfer.")
    lines.append(" * Once the transport contract is simplified, this helper can collapse")
    lines.append(" * back to a single-phase transfer without changing the public API.")
    lines.append(" */")
    lines.append("#define PERIPHX_DEBUG_DEFERRED_READBACK 1u")
    lines.append(f"#define PERIPHX_DEBUG_READBACK_TOKEN 0x{TURNAROUND_BYTE:02X}u")
    lines.append("")
    lines.append("typedef enum {")
    lines.append("    PERIPHX_OK = 0,")
    lines.append("    PERIPHX_ERR_IO = -1,")
    lines.append("    PERIPHX_ERR_FRAME = -2,")
    lines.append("    PERIPHX_ERR_CRC = -3,")
    lines.append("    PERIPHX_ERR_RESPONSE = -4,")
    lines.append("} periphx_status_t;")
    lines.append("")
    lines.append(
        "typedef int (*periphx_transport_fn)(void *user, const uint8_t *tx, uint8_t *rx, size_t len);"
    )
    lines.append("")
    lines.append("typedef struct {")
    lines.append("    periphx_transport_fn transfer;")
    lines.append("    void *user;")
    lines.append("} periphx_device_t;")
    lines.append("")
    lines.append("typedef struct {")
    lines.append("    uint8_t server_id;")
    lines.append("    uint32_t payload;")
    lines.append("    uint8_t msg_type;")
    lines.append("    uint8_t crc4;")
    lines.append("} periphx_frame_t;")
    lines.append("")
    for service in spec.services:
        macro = service.c_macro_name
        lines.append(f"#define {macro} {service.service_id}u")
    lines.append("")
    lines.append("void periphx_device_init(periphx_device_t *dev, periphx_transport_fn transfer, void *user);")
    lines.append(
        "int periphx_transfer_frame(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response);"
    )
    lines.append("int periphx_call_u32(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t *response_value);")
    lines.append("int periphx_call_u8(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t *response_value);")
    lines.append("int periphx_call_bool(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t *response_value);")
    lines.append("")
    for service in spec.services:
        c_fn = service.c_function_name
        type_name = _c_type_name(service.data_type)
        lines.append(
            f"int {c_fn}(periphx_device_t *dev, {type_name} value, uint32_t *response_value);"
        )
    lines.append("")
    lines.append("#endif /* PERIPHX_SDK_H */")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_sdk_source(spec: ProjectSpec, path: Path) -> Path:
    lines: list[str] = []
    lines.append('#include "periphx_sdk.h"')
    lines.append("")
    lines.append("static uint8_t crc4_step(uint8_t crc_in, uint8_t bit_in)")
    lines.append("{")
    lines.append("    uint8_t feedback = (uint8_t)(((crc_in >> 3) ^ bit_in) & 0x1u);")
    lines.append("    uint8_t crc_out = (uint8_t)((crc_in << 1) & 0xFu);")
    lines.append("    if(feedback) {")
    lines.append("        crc_out ^= 0x3u;")
    lines.append("    }")
    lines.append("    return (uint8_t)(crc_out & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("static uint8_t crc4_byte(uint8_t crc_in, uint8_t data)")
    lines.append("{")
    lines.append("    for(int bit = 7; bit >= 0; --bit) {")
    lines.append("        crc_in = crc4_step(crc_in, (uint8_t)((data >> bit) & 0x1u));")
    lines.append("    }")
    lines.append("    return (uint8_t)(crc_in & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("static uint8_t crc4_nibble(uint8_t crc_in, uint8_t data)")
    lines.append("{")
    lines.append("    for(int bit = 3; bit >= 0; --bit) {")
    lines.append("        crc_in = crc4_step(crc_in, (uint8_t)((data >> bit) & 0x1u));")
    lines.append("    }")
    lines.append("    return (uint8_t)(crc_in & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("static uint8_t crc4_frame(const periphx_frame_t *frame)")
    lines.append("{")
    lines.append("    uint8_t crc = 0u;")
    lines.append("    crc = crc4_byte(crc, frame->server_id);")
    lines.append("    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 24));")
    lines.append("    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 16));")
    lines.append("    crc = crc4_byte(crc, (uint8_t)(frame->payload >> 8));")
    lines.append("    crc = crc4_byte(crc, (uint8_t)frame->payload);")
    lines.append("    crc = crc4_nibble(crc, frame->msg_type);")
    lines.append("    return (uint8_t)(crc & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("static void pack_frame(const periphx_frame_t *frame, uint8_t bytes[PERIPHX_FRAME_LEN])")
    lines.append("{")
    lines.append("    bytes[0] = frame->server_id;")
    lines.append("    bytes[1] = (uint8_t)(frame->payload >> 24);")
    lines.append("    bytes[2] = (uint8_t)(frame->payload >> 16);")
    lines.append("    bytes[3] = (uint8_t)(frame->payload >> 8);")
    lines.append("    bytes[4] = (uint8_t)frame->payload;")
    lines.append("    bytes[5] = (uint8_t)(((frame->crc4 & 0xFu) << 4) | (frame->msg_type & 0xFu));")
    lines.append("}")
    lines.append("")
    lines.append("static void unpack_frame(periphx_frame_t *frame, const uint8_t bytes[PERIPHX_FRAME_LEN])")
    lines.append("{")
    lines.append("    frame->server_id = bytes[0];")
    lines.append("    frame->payload = ((uint32_t)bytes[1] << 24) | ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 8) | (uint32_t)bytes[4];")
    lines.append("    frame->msg_type = (uint8_t)(bytes[5] & 0xFu);")
    lines.append("    frame->crc4 = (uint8_t)((bytes[5] >> 4) & 0xFu);")
    lines.append("}")
    lines.append("")
    lines.append("void periphx_device_init(periphx_device_t *dev, periphx_transport_fn transfer, void *user)")
    lines.append("{")
    lines.append("    dev->transfer = transfer;")
    lines.append("    dev->user = user;")
    lines.append("}")
    lines.append("")
    lines.append("static int transfer_bytes(periphx_device_t *dev, const uint8_t *tx_bytes, uint8_t *rx_bytes, size_t len)")
    lines.append("{")
    lines.append("    if(dev->transfer == NULL) {")
    lines.append("        return PERIPHX_ERR_IO;")
    lines.append("    }")
    lines.append("    if(dev->transfer(dev->user, tx_bytes, rx_bytes, len) != 0) {")
    lines.append("        return PERIPHX_ERR_IO;")
    lines.append("    }")
    lines.append("    return PERIPHX_OK;")
    lines.append("}")
    lines.append("")
    lines.append("int periphx_transfer_frame(periphx_device_t *dev, const periphx_frame_t *request, periphx_frame_t *response)")
    lines.append("{")
    lines.append("    uint8_t tx_bytes[PERIPHX_TRANSACTION_LEN];")
    lines.append("    uint8_t rx_bytes[PERIPHX_TRANSACTION_LEN];")
    lines.append("    periphx_frame_t tmp = *request;")
    lines.append("    tmp.msg_type &= 0xFu;")
    lines.append("    tmp.crc4 = crc4_frame(&tmp);")
    lines.append("    pack_frame(&tmp, tx_bytes);")
    lines.append("    #if PERIPHX_DEBUG_DEFERRED_READBACK")
    lines.append("    for(size_t i = 0; i < PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN; ++i) {")
    lines.append("        tx_bytes[PERIPHX_FRAME_LEN + i] = PERIPHX_DEBUG_READBACK_TOKEN;")
    lines.append("    }")
    lines.append("    #else")
    lines.append("    for(size_t i = 0; i < PERIPHX_TURNAROUND_LEN + PERIPHX_FRAME_LEN; ++i) {")
    lines.append(f"        tx_bytes[PERIPHX_FRAME_LEN + i] = 0x{TURNAROUND_BYTE:02X}u;")
    lines.append("    }")
    lines.append("    #endif")
    lines.append("    /*")
    lines.append("     * Transaction layout:")
    lines.append("     *   - bytes 0..5  : request frame")
    lines.append("     *   - bytes 6..8  : byte-alignment window")
    lines.append("     *   - bytes 9..14 : readback frame")
    lines.append("     * The alignment window is part of the current transport contract and")
    lines.append("     * keeps the response byte boundary stable while the FPGA bridge drains")
    lines.append("     * the request through parse/router/component logic.")
    lines.append("     */")
    lines.append("    if(transfer_bytes(dev, tx_bytes, rx_bytes, PERIPHX_TRANSACTION_LEN) != PERIPHX_OK) {")
    lines.append("        return PERIPHX_ERR_IO;")
    lines.append("    }")
    lines.append("    unpack_frame(response, rx_bytes + PERIPHX_FRAME_LEN + PERIPHX_TURNAROUND_LEN);")
    lines.append("    if(crc4_frame(response) != response->crc4) {")
    lines.append("        return PERIPHX_ERR_CRC;")
    lines.append("    }")
    lines.append("    if(response->server_id != request->server_id) {")
    lines.append("        return PERIPHX_ERR_RESPONSE;")
    lines.append("    }")
    lines.append("    return PERIPHX_OK;")
    lines.append("}")
    lines.append("")
    lines.append("int periphx_call_u32(periphx_device_t *dev, uint8_t service_id, uint32_t value, uint32_t *response_value)")
    lines.append("{")
    lines.append("    periphx_frame_t request = { service_id, value, PERIPHX_MSG_REQUEST, 0u };")
    lines.append("    periphx_frame_t response = {0};")
    lines.append("    int status = periphx_transfer_frame(dev, &request, &response);")
    lines.append("    if(status != PERIPHX_OK) {")
    lines.append("        return status;")
    lines.append("    }")
    lines.append("    if(response.msg_type == PERIPHX_MSG_ERROR) {")
    lines.append("        return PERIPHX_ERR_RESPONSE;")
    lines.append("    }")
    lines.append("    if(response.msg_type != PERIPHX_MSG_RESPONSE) {")
    lines.append("        return PERIPHX_ERR_RESPONSE;")
    lines.append("    }")
    lines.append("    if(response_value != NULL) {")
    lines.append("        *response_value = response.payload;")
    lines.append("    }")
    lines.append("    return PERIPHX_OK;")
    lines.append("}")
    lines.append("")
    lines.append("int periphx_call_u8(periphx_device_t *dev, uint8_t service_id, uint8_t value, uint32_t *response_value)")
    lines.append("{")
    lines.append("    return periphx_call_u32(dev, service_id, (uint32_t)value, response_value);")
    lines.append("}")
    lines.append("")
    lines.append("int periphx_call_bool(periphx_device_t *dev, uint8_t service_id, bool value, uint32_t *response_value)")
    lines.append("{")
    lines.append("    return periphx_call_u32(dev, service_id, value ? 1u : 0u, response_value);")
    lines.append("}")
    lines.append("")
    for service in spec.services:
        c_fn = service.c_function_name
        type_name = _c_type_name(service.data_type)
        lines.append(
            f"int {c_fn}(periphx_device_t *dev, {type_name} value, uint32_t *response_value)"
        )
        lines.append("{")
        if service.data_type == "bool":
            lines.append(
                f"    return periphx_call_bool(dev, {service.c_macro_name}, value, response_value);"
            )
        elif service.data_type == "u8":
            lines.append(
                f"    return periphx_call_u8(dev, {service.c_macro_name}, value, response_value);"
            )
        else:
            lines.append(
                f"    return periphx_call_u32(dev, {service.c_macro_name}, value, response_value);"
            )
        lines.append("}")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_generated_rtl(spec: ProjectSpec, path: Path) -> Path:
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
            lines.extend(_emit_pwm_led_adapter())
        else:
            raise NotImplementedError(
                f"component type {component_type!r} is not supported by the current generator"
            )
        lines.append("")

    lines.extend(_emit_top_module(spec))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _emit_pwm_led_adapter() -> list[str]:
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


def _emit_top_module(spec: ProjectSpec) -> list[str]:
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
            direction = "output" if _is_output_pin(component, pin_name) else "input"
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
    lines.append("    wire [NUM_SLOTS*8-1:0] slot_service_ids;")
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
    lines.append("        for(slot_i = 0; slot_i < NUM_SLOTS; slot_i = slot_i + 1) begin : gen_slot_map")
    lines.append("            assign slot_service_ids[(slot_i*8) +: 8] = slot_i[7:0];")
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
    lines.append("        .slot_service_ids  (slot_service_ids),")
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
        if component.component_type != "pwm_led":
            raise NotImplementedError(
                f"component type {component.component_type!r} is not supported by the current generator"
            )
        lines.extend(_emit_pwm_led_instance(spec, component))
        lines.append("")

    lines.append("endmodule")
    return lines


def _emit_pwm_led_instance(spec: ProjectSpec, component: ComponentSpec) -> list[str]:
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


def _c_type_name(data_type: str) -> str:
    if data_type == "bool":
        return "bool"
    if data_type == "u8":
        return "uint8_t"
    return "uint32_t"


def _is_output_pin(component: ComponentSpec, pin_name: str) -> bool:
    if component.component_type == "pwm_led":
        return pin_name == "led_pwm"
    return True
