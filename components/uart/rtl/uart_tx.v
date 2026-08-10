module uart_tx(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] baud_div,
    input  wire [2:0]  data_bits_code,
    input  wire [1:0]  parity,
    input  wire        stop_bits_code,
    input  wire        tx_valid,
    input  wire [7:0]  tx_data,
    output wire        tx_ready,
    output reg         tx_busy,
    output reg         uart_txd
);

localparam [1:0] PARITY_NONE = 2'd0;
localparam [1:0] PARITY_ODD  = 2'd1;
localparam [1:0] PARITY_EVEN = 2'd2;

reg [15:0] baud_div_r;
reg [15:0] baud_cnt;
reg [7:0]  data_r;
reg [2:0]  data_bits_code_r;
reg [1:0]  parity_r;
reg        stop_bits_code_r;
reg [3:0]  bit_index;
reg [3:0]  total_bits;
reg        parity_bit_r;

wire [3:0] data_bits_count;
wire [3:0] parity_bits_count;
wire [3:0] stop_bits_count;
wire [3:0] total_bits_next;
wire       data_parity;
wire       sample_last;
wire       baud_tick;

assign tx_ready = !tx_busy;
assign data_bits_count = {1'b0, data_bits_code} + 4'd5;
assign parity_bits_count = (parity == PARITY_NONE) ? 4'd0 : 4'd1;
assign stop_bits_count = stop_bits_code ? 4'd2 : 4'd1;
assign total_bits_next = 4'd1 + data_bits_count + parity_bits_count + stop_bits_count;
assign data_parity = ^(tx_data & data_mask(data_bits_count));
assign sample_last = (bit_index == (total_bits - 4'd1));
assign baud_tick = (baud_cnt >= (baud_div_r - 16'd1));

function [7:0] data_mask;
    input [3:0] bit_count;
    begin
        case(bit_count)
            4'd5: data_mask = 8'h1F;
            4'd6: data_mask = 8'h3F;
            4'd7: data_mask = 8'h7F;
            default: data_mask = 8'hFF;
        endcase
    end
endfunction

function parity_value;
    input data_parity_in;
    input [1:0] parity_mode;
    begin
        if(parity_mode == PARITY_ODD) begin
            parity_value = ~data_parity_in;
        end else begin
            parity_value = data_parity_in;
        end
    end
endfunction

function bit_value;
    input [3:0] index;
    input [3:0] data_count;
    input [1:0] parity_mode;
    input [7:0] data_value;
    input parity_value_in;
    begin
        if(index == 4'd0) begin
            bit_value = 1'b0;
        end else if(index <= data_count) begin
            bit_value = data_value[index - 4'd1];
        end else if((parity_mode != PARITY_NONE) && (index == (data_count + 4'd1))) begin
            bit_value = parity_value_in;
        end else begin
            bit_value = 1'b1;
        end
    end
endfunction

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        tx_busy <= 1'b0;
        uart_txd <= 1'b1;
        baud_div_r <= 16'd1;
        baud_cnt <= 16'd0;
        data_r <= 8'd0;
        data_bits_code_r <= 3'd3;
        parity_r <= PARITY_NONE;
        stop_bits_code_r <= 1'b0;
        bit_index <= 4'd0;
        total_bits <= 4'd10;
        parity_bit_r <= 1'b0;
    end else begin
        if(!tx_busy) begin
            baud_cnt <= 16'd0;
            bit_index <= 4'd0;
            uart_txd <= 1'b1;
            if(tx_valid) begin
                tx_busy <= 1'b1;
                baud_div_r <= baud_div;
                data_r <= tx_data;
                data_bits_code_r <= data_bits_code;
                parity_r <= parity;
                stop_bits_code_r <= stop_bits_code;
                total_bits <= total_bits_next;
                parity_bit_r <= parity_value(data_parity, parity);
                uart_txd <= 1'b0;
            end
        end else begin
            if(baud_tick) begin
                baud_cnt <= 16'd0;
                if(sample_last) begin
                    tx_busy <= 1'b0;
                    bit_index <= 4'd0;
                    uart_txd <= 1'b1;
                end else begin
                    bit_index <= bit_index + 4'd1;
                    uart_txd <= bit_value(
                        bit_index + 4'd1,
                        {1'b0, data_bits_code_r} + 4'd5,
                        parity_r,
                        data_r,
                        parity_bit_r
                    );
                end
            end else begin
                baud_cnt <= baud_cnt + 16'd1;
            end
        end
    end
end

endmodule
