module i2c_master #(
    parameter integer DEFAULT_CLK_DIV = 250,
    parameter integer DEFAULT_STRETCH_TIMEOUT = 1024,
    parameter integer BUFFER_DEPTH = 16
)(
    input  wire         clk,
    input  wire         rst_n,

    input  wire         start,
    input  wire         rw,
    input  wire [6:0]   dev_addr,
    input  wire [7:0]   reg_addr,
    input  wire [7:0]   length,
    input  wire [127:0] tx_data,
    input  wire [31:0]  clk_div,
    input  wire [31:0]  stretch_timeout,

    output wire         busy,
    output reg          done,
    output reg          read_valid,
    output reg  [7:0]   read_data,
    output reg  [7:0]   rx_count,
    output reg          ack_error,
    output reg          stretch_timeout_error,
    output reg          arb_lost,
    output reg  [3:0]   error_code,

    inout  wire         i2c_scl,
    inout  wire         i2c_sda
);

localparam [5:0] ST_IDLE            = 6'd0;
localparam [5:0] ST_START_RELEASE   = 6'd1;
localparam [5:0] ST_START_DRIVE     = 6'd2;
localparam [5:0] ST_START_FALL      = 6'd3;
localparam [5:0] ST_BIT_SETUP       = 6'd4;
localparam [5:0] ST_BIT_HIGH        = 6'd5;
localparam [5:0] ST_BIT_FALL        = 6'd6;
localparam [5:0] ST_ACK_SETUP       = 6'd7;
localparam [5:0] ST_ACK_HIGH        = 6'd8;
localparam [5:0] ST_ACK_FALL        = 6'd9;
localparam [5:0] ST_RESTART_PREP    = 6'd10;
localparam [5:0] ST_RESTART_HIGH    = 6'd11;
localparam [5:0] ST_RESTART_DRIVE   = 6'd12;
localparam [5:0] ST_RESTART_FALL    = 6'd13;
localparam [5:0] ST_READ_SETUP      = 6'd14;
localparam [5:0] ST_READ_HIGH       = 6'd15;
localparam [5:0] ST_READ_FALL       = 6'd16;
localparam [5:0] ST_MACK_SETUP      = 6'd17;
localparam [5:0] ST_MACK_HIGH       = 6'd18;
localparam [5:0] ST_MACK_FALL       = 6'd19;
localparam [5:0] ST_STOP_SETUP      = 6'd20;
localparam [5:0] ST_STOP_HIGH       = 6'd21;
localparam [5:0] ST_STOP_RELEASE    = 6'd22;

localparam [1:0] BYTE_ADDR_W = 2'd0;
localparam [1:0] BYTE_REG    = 2'd1;
localparam [1:0] BYTE_DATA   = 2'd2;
localparam [1:0] BYTE_ADDR_R = 2'd3;

localparam [3:0] ERR_NONE             = 4'd0;
localparam [3:0] ERR_ADDR_WRITE_NACK  = 4'd1;
localparam [3:0] ERR_REG_ADDR_NACK    = 4'd2;
localparam [3:0] ERR_WRITE_DATA_NACK  = 4'd3;
localparam [3:0] ERR_ADDR_READ_NACK   = 4'd4;
localparam [3:0] ERR_STRETCH_TIMEOUT  = 4'd5;
localparam [3:0] ERR_ARB_LOST         = 4'd6;
localparam [3:0] ERR_INVALID_LENGTH   = 4'd7;

localparam [31:0] DEFAULT_CLK_DIV_VALUE = DEFAULT_CLK_DIV;
localparam [31:0] DEFAULT_STRETCH_TIMEOUT_VALUE = DEFAULT_STRETCH_TIMEOUT;

reg [5:0]   state;
reg [31:0]  div_count;
reg [31:0]  active_div;
reg [31:0]  stretch_count;
reg [31:0]  active_stretch_timeout;
reg         rw_r;
reg [6:0]   dev_addr_r;
reg [7:0]   reg_addr_r;
reg [7:0]   length_r;
reg [127:0] tx_data_r;
reg [7:0]   tx_byte;
reg [7:0]   rx_byte;
reg [2:0]   bit_index;
reg [3:0]   byte_index;
reg [1:0]   byte_phase;
reg         master_ack_bit;
reg         scl_drive_low;
reg         sda_drive_low;

wire scl_high_wait_state;

assign busy = (state != ST_IDLE);
assign i2c_scl = scl_drive_low ? 1'b0 : 1'bz;
assign i2c_sda = sda_drive_low ? 1'b0 : 1'bz;
assign scl_high_wait_state =
    (state == ST_START_RELEASE) ||
    (state == ST_BIT_HIGH) ||
    (state == ST_ACK_HIGH) ||
    (state == ST_RESTART_HIGH) ||
    (state == ST_READ_HIGH) ||
    (state == ST_MACK_HIGH) ||
    (state == ST_STOP_HIGH);

function [31:0] normalize_div;
    input [31:0] value;
    begin
        if(value == 32'd0) begin
            normalize_div = DEFAULT_CLK_DIV_VALUE;
        end else if(value < 32'd2) begin
            normalize_div = 32'd2;
        end else begin
            normalize_div = value;
        end
    end
endfunction

function [31:0] normalize_timeout;
    input [31:0] value;
    begin
        if(value == 32'd0) begin
            normalize_timeout = DEFAULT_STRETCH_TIMEOUT_VALUE;
        end else begin
            normalize_timeout = value;
        end
    end
endfunction

function [7:0] get_tx_byte;
    input [127:0] data;
    input [3:0]   index;
    begin
        case(index)
            4'd0:  get_tx_byte = data[7:0];
            4'd1:  get_tx_byte = data[15:8];
            4'd2:  get_tx_byte = data[23:16];
            4'd3:  get_tx_byte = data[31:24];
            4'd4:  get_tx_byte = data[39:32];
            4'd5:  get_tx_byte = data[47:40];
            4'd6:  get_tx_byte = data[55:48];
            4'd7:  get_tx_byte = data[63:56];
            4'd8:  get_tx_byte = data[71:64];
            4'd9:  get_tx_byte = data[79:72];
            4'd10: get_tx_byte = data[87:80];
            4'd11: get_tx_byte = data[95:88];
            4'd12: get_tx_byte = data[103:96];
            4'd13: get_tx_byte = data[111:104];
            4'd14: get_tx_byte = data[119:112];
            4'd15: get_tx_byte = data[127:120];
            default: get_tx_byte = 8'd0;
        endcase
    end
endfunction

function [3:0] phase_error_code;
    input [1:0] phase;
    begin
        case(phase)
            BYTE_ADDR_W: phase_error_code = ERR_ADDR_WRITE_NACK;
            BYTE_REG:    phase_error_code = ERR_REG_ADDR_NACK;
            BYTE_DATA:   phase_error_code = ERR_WRITE_DATA_NACK;
            BYTE_ADDR_R: phase_error_code = ERR_ADDR_READ_NACK;
            default:     phase_error_code = ERR_NONE;
        endcase
    end
endfunction

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        state                 <= ST_IDLE;
        div_count             <= 32'd0;
        active_div            <= DEFAULT_CLK_DIV_VALUE;
        stretch_count         <= 32'd0;
        active_stretch_timeout <= DEFAULT_STRETCH_TIMEOUT_VALUE;
        rw_r                  <= 1'b0;
        dev_addr_r            <= 7'd0;
        reg_addr_r            <= 8'd0;
        length_r              <= 8'd0;
        tx_data_r             <= 128'd0;
        tx_byte               <= 8'd0;
        rx_byte               <= 8'd0;
        bit_index             <= 3'd0;
        byte_index            <= 4'd0;
        byte_phase            <= BYTE_ADDR_W;
        master_ack_bit        <= 1'b0;
        scl_drive_low         <= 1'b0;
        sda_drive_low         <= 1'b0;
        done                  <= 1'b0;
        read_valid            <= 1'b0;
        read_data             <= 8'd0;
        rx_count              <= 8'd0;
        ack_error             <= 1'b0;
        stretch_timeout_error <= 1'b0;
        arb_lost              <= 1'b0;
        error_code            <= ERR_NONE;
    end else begin
        done                  <= 1'b0;
        read_valid            <= 1'b0;
        ack_error             <= 1'b0;
        stretch_timeout_error <= 1'b0;
        arb_lost              <= 1'b0;

        if(state == ST_IDLE) begin
            scl_drive_low <= 1'b0;
            sda_drive_low <= 1'b0;
            div_count <= 32'd0;
            stretch_count <= 32'd0;

            if(start) begin
                active_div <= normalize_div(clk_div);
                active_stretch_timeout <= normalize_timeout(stretch_timeout);
                rw_r <= rw;
                dev_addr_r <= dev_addr;
                reg_addr_r <= reg_addr;
                length_r <= length;
                tx_data_r <= tx_data;
                tx_byte <= {dev_addr, 1'b0};
                rx_byte <= 8'd0;
                bit_index <= 3'd7;
                byte_index <= 4'd0;
                byte_phase <= BYTE_ADDR_W;
                rx_count <= 8'd0;
                error_code <= ERR_NONE;
                div_count <= normalize_div(clk_div) - 32'd1;
                stretch_count <= 32'd0;
                if((length == 8'd0) || (length > 8'd16)) begin
                    error_code <= ERR_INVALID_LENGTH;
                    ack_error <= 1'b1;
                    done <= 1'b1;
                    state <= ST_IDLE;
                end else begin
                    state <= ST_START_RELEASE;
                end
            end
        end else if(scl_high_wait_state && (i2c_scl == 1'b0)) begin
            scl_drive_low <= 1'b0;
            if(stretch_count >= active_stretch_timeout) begin
                stretch_timeout_error <= 1'b1;
                error_code <= ERR_STRETCH_TIMEOUT;
                scl_drive_low <= 1'b0;
                sda_drive_low <= 1'b0;
                div_count <= 32'd0;
                stretch_count <= 32'd0;
                done <= 1'b1;
                state <= ST_IDLE;
            end else begin
                stretch_count <= stretch_count + 32'd1;
            end
        end else if(div_count != 32'd0) begin
            if(scl_high_wait_state) begin
                scl_drive_low <= 1'b0;
                stretch_count <= 32'd0;
            end
            div_count <= div_count - 32'd1;
        end else begin
            stretch_count <= 32'd0;
            div_count <= active_div - 32'd1;

            case(state)
                ST_START_RELEASE: begin
                    scl_drive_low <= 1'b0;
                    sda_drive_low <= 1'b0;
                    state <= ST_START_DRIVE;
                end

                ST_START_DRIVE: begin
                    scl_drive_low <= 1'b0;
                    sda_drive_low <= 1'b1;
                    state <= ST_START_FALL;
                end

                ST_START_FALL: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= 1'b1;
                    tx_byte <= {dev_addr_r, 1'b0};
                    bit_index <= 3'd7;
                    byte_phase <= BYTE_ADDR_W;
                    state <= ST_BIT_SETUP;
                end

                ST_BIT_SETUP: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= (tx_byte[bit_index] == 1'b0) ? 1'b1 : 1'b0;
                    state <= ST_BIT_HIGH;
                end

                ST_BIT_HIGH: begin
                    scl_drive_low <= 1'b0;
                    if((tx_byte[bit_index] == 1'b1) && (i2c_sda == 1'b0)) begin
                        arb_lost <= 1'b1;
                        error_code <= ERR_ARB_LOST;
                        scl_drive_low <= 1'b0;
                        sda_drive_low <= 1'b0;
                        div_count <= 32'd0;
                        done <= 1'b1;
                        state <= ST_IDLE;
                    end else begin
                        state <= ST_BIT_FALL;
                    end
                end

                ST_BIT_FALL: begin
                    scl_drive_low <= 1'b1;
                    if(bit_index == 3'd0) begin
                        state <= ST_ACK_SETUP;
                    end else begin
                        bit_index <= bit_index - 3'd1;
                        state <= ST_BIT_SETUP;
                    end
                end

                ST_ACK_SETUP: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= 1'b0;
                    state <= ST_ACK_HIGH;
                end

                ST_ACK_HIGH: begin
                    scl_drive_low <= 1'b0;
                    if(i2c_sda == 1'b1) begin
                        ack_error <= 1'b1;
                        error_code <= phase_error_code(byte_phase);
                        state <= ST_STOP_SETUP;
                    end else begin
                        state <= ST_ACK_FALL;
                    end
                end

                ST_ACK_FALL: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= 1'b0;
                    case(byte_phase)
                        BYTE_ADDR_W: begin
                            tx_byte <= reg_addr_r;
                            bit_index <= 3'd7;
                            byte_phase <= BYTE_REG;
                            state <= ST_BIT_SETUP;
                        end

                        BYTE_REG: begin
                            if(rw_r) begin
                                state <= ST_RESTART_PREP;
                            end else begin
                                byte_index <= 4'd0;
                                tx_byte <= get_tx_byte(tx_data_r, 4'd0);
                                bit_index <= 3'd7;
                                byte_phase <= BYTE_DATA;
                                state <= ST_BIT_SETUP;
                            end
                        end

                        BYTE_DATA: begin
                            if({4'd0, byte_index} < (length_r - 8'd1)) begin
                                byte_index <= byte_index + 4'd1;
                                tx_byte <= get_tx_byte(tx_data_r, byte_index + 4'd1);
                                bit_index <= 3'd7;
                                state <= ST_BIT_SETUP;
                            end else begin
                                state <= ST_STOP_SETUP;
                            end
                        end

                        BYTE_ADDR_R: begin
                            byte_index <= 4'd0;
                            bit_index <= 3'd7;
                            rx_byte <= 8'd0;
                            state <= ST_READ_SETUP;
                        end

                        default: begin
                            state <= ST_STOP_SETUP;
                        end
                    endcase
                end

                ST_RESTART_PREP: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= 1'b0;
                    state <= ST_RESTART_HIGH;
                end

                ST_RESTART_HIGH: begin
                    scl_drive_low <= 1'b0;
                    sda_drive_low <= 1'b0;
                    state <= ST_RESTART_DRIVE;
                end

                ST_RESTART_DRIVE: begin
                    scl_drive_low <= 1'b0;
                    sda_drive_low <= 1'b1;
                    state <= ST_RESTART_FALL;
                end

                ST_RESTART_FALL: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= 1'b1;
                    tx_byte <= {dev_addr_r, 1'b1};
                    bit_index <= 3'd7;
                    byte_phase <= BYTE_ADDR_R;
                    state <= ST_BIT_SETUP;
                end

                ST_READ_SETUP: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= 1'b0;
                    state <= ST_READ_HIGH;
                end

                ST_READ_HIGH: begin
                    scl_drive_low <= 1'b0;
                    rx_byte[bit_index] <= i2c_sda;
                    state <= ST_READ_FALL;
                end

                ST_READ_FALL: begin
                    scl_drive_low <= 1'b1;
                    if(bit_index == 3'd0) begin
                        master_ack_bit <= (byte_index < (length_r[3:0] - 4'd1));
                        state <= ST_MACK_SETUP;
                    end else begin
                        bit_index <= bit_index - 3'd1;
                        state <= ST_READ_SETUP;
                    end
                end

                ST_MACK_SETUP: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= master_ack_bit ? 1'b1 : 1'b0;
                    state <= ST_MACK_HIGH;
                end

                ST_MACK_HIGH: begin
                    scl_drive_low <= 1'b0;
                    state <= ST_MACK_FALL;
                end

                ST_MACK_FALL: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= 1'b0;
                    read_data <= rx_byte;
                    read_valid <= 1'b1;
                    rx_count <= rx_count + 8'd1;
                    if(byte_index < (length_r[3:0] - 4'd1)) begin
                        byte_index <= byte_index + 4'd1;
                        bit_index <= 3'd7;
                        rx_byte <= 8'd0;
                        state <= ST_READ_SETUP;
                    end else begin
                        state <= ST_STOP_SETUP;
                    end
                end

                ST_STOP_SETUP: begin
                    scl_drive_low <= 1'b1;
                    sda_drive_low <= 1'b1;
                    state <= ST_STOP_HIGH;
                end

                ST_STOP_HIGH: begin
                    scl_drive_low <= 1'b0;
                    sda_drive_low <= 1'b1;
                    state <= ST_STOP_RELEASE;
                end

                ST_STOP_RELEASE: begin
                    scl_drive_low <= 1'b0;
                    sda_drive_low <= 1'b0;
                    done <= 1'b1;
                    state <= ST_IDLE;
                end

                default: begin
                    scl_drive_low <= 1'b0;
                    sda_drive_low <= 1'b0;
                    state <= ST_IDLE;
                end
            endcase
        end
    end
end

endmodule
