module uart_rx(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] baud_div,
    input  wire [2:0]  data_bits_code,
    input  wire [1:0]  parity,
    input  wire        stop_bits_code,
    input  wire        uart_rxd,
    output reg         rx_valid,
    output reg  [7:0]  rx_data,
    output reg         parity_error,
    output reg         frame_error
);

localparam [1:0] PARITY_NONE = 2'd0;
localparam [1:0] PARITY_ODD  = 2'd1;
localparam [1:0] PARITY_EVEN = 2'd2;
localparam [2:0] ST_IDLE     = 3'd0;
localparam [2:0] ST_START    = 3'd1;
localparam [2:0] ST_DATA     = 3'd2;
localparam [2:0] ST_PARITY   = 3'd3;
localparam [2:0] ST_STOP     = 3'd4;

reg       rxd_d0;
reg       rxd_d1;
reg       rxd_prev;
reg [2:0] state;
reg [15:0] baud_div_r;
reg [15:0] baud_cnt;
reg [2:0] data_bits_code_r;
reg [1:0] parity_r;
reg       stop_bits_code_r;
reg [3:0] data_bits_count_r;
reg [3:0] data_index;
reg [1:0] stop_index;
reg [7:0] data_shift;
reg       parity_calc;
reg       parity_error_pending;
reg       frame_error_pending;

wire start_edge;
wire baud_tick;
wire half_tick;
wire sampled_bit;
wire expected_parity;
wire [1:0] stop_count;

assign start_edge = rxd_prev && !rxd_d1;
assign baud_tick = (baud_cnt >= (baud_div_r - 16'd1));
assign half_tick = (baud_cnt >= ({1'b0, baud_div_r[15:1]}));
assign sampled_bit = rxd_d1;
assign expected_parity = (parity_r == PARITY_ODD) ? ~parity_calc : parity_calc;
assign stop_count = stop_bits_code_r ? 2'd2 : 2'd1;

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        rxd_d0 <= 1'b1;
        rxd_d1 <= 1'b1;
        rxd_prev <= 1'b1;
    end else begin
        rxd_d0 <= uart_rxd;
        rxd_d1 <= rxd_d0;
        rxd_prev <= rxd_d1;
    end
end

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        state <= ST_IDLE;
        baud_div_r <= 16'd1;
        baud_cnt <= 16'd0;
        data_bits_code_r <= 3'd3;
        parity_r <= PARITY_NONE;
        stop_bits_code_r <= 1'b0;
        data_bits_count_r <= 4'd8;
        data_index <= 4'd0;
        stop_index <= 2'd0;
        data_shift <= 8'd0;
        parity_calc <= 1'b0;
        parity_error_pending <= 1'b0;
        frame_error_pending <= 1'b0;
        rx_valid <= 1'b0;
        rx_data <= 8'd0;
        parity_error <= 1'b0;
        frame_error <= 1'b0;
    end else begin
        rx_valid <= 1'b0;
        parity_error <= 1'b0;
        frame_error <= 1'b0;

        case(state)
            ST_IDLE: begin
                baud_cnt <= 16'd0;
                data_index <= 4'd0;
                stop_index <= 2'd0;
                parity_error_pending <= 1'b0;
                frame_error_pending <= 1'b0;
                if(start_edge) begin
                    state <= ST_START;
                    baud_div_r <= baud_div;
                    data_bits_code_r <= data_bits_code;
                    parity_r <= parity;
                    stop_bits_code_r <= stop_bits_code;
                    data_bits_count_r <= {1'b0, data_bits_code} + 4'd5;
                    data_shift <= 8'd0;
                    parity_calc <= 1'b0;
                end
            end
            ST_START: begin
                if(half_tick) begin
                    baud_cnt <= 16'd0;
                    if(sampled_bit == 1'b0) begin
                        state <= ST_DATA;
                    end else begin
                        state <= ST_IDLE;
                        frame_error <= 1'b1;
                    end
                end else begin
                    baud_cnt <= baud_cnt + 16'd1;
                end
            end
            ST_DATA: begin
                if(baud_tick) begin
                    baud_cnt <= 16'd0;
                    data_shift[data_index] <= sampled_bit;
                    parity_calc <= parity_calc ^ sampled_bit;
                    if(data_index == (data_bits_count_r - 4'd1)) begin
                        data_index <= 4'd0;
                        if(parity_r == PARITY_NONE) begin
                            state <= ST_STOP;
                        end else begin
                            state <= ST_PARITY;
                        end
                    end else begin
                        data_index <= data_index + 4'd1;
                    end
                end else begin
                    baud_cnt <= baud_cnt + 16'd1;
                end
            end
            ST_PARITY: begin
                if(baud_tick) begin
                    baud_cnt <= 16'd0;
                    if(sampled_bit != expected_parity) begin
                        parity_error_pending <= 1'b1;
                    end
                    state <= ST_STOP;
                end else begin
                    baud_cnt <= baud_cnt + 16'd1;
                end
            end
            ST_STOP: begin
                if(baud_tick) begin
                    baud_cnt <= 16'd0;
                    if(sampled_bit != 1'b1) begin
                        frame_error_pending <= 1'b1;
                    end
                    if(stop_index == (stop_count - 2'd1)) begin
                        state <= ST_IDLE;
                        if((sampled_bit == 1'b1) && !frame_error_pending && !parity_error_pending) begin
                            rx_valid <= 1'b1;
                            rx_data <= mask_data(data_shift, data_bits_count_r);
                        end else begin
                            parity_error <= parity_error_pending;
                            frame_error <= frame_error_pending || (sampled_bit != 1'b1);
                        end
                    end else begin
                        stop_index <= stop_index + 2'd1;
                    end
                end else begin
                    baud_cnt <= baud_cnt + 16'd1;
                end
            end
            default: begin
                state <= ST_IDLE;
            end
        endcase
    end
end

function [7:0] mask_data;
    input [7:0] value;
    input [3:0] bit_count;
    begin
        case(bit_count)
            4'd5: mask_data = value & 8'h1F;
            4'd6: mask_data = value & 8'h3F;
            4'd7: mask_data = value & 8'h7F;
            default: mask_data = value;
        endcase
    end
endfunction

endmodule
