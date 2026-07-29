module uart_tx(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    input  wire [31:0] baud_div,
    input  wire [7:0]  tx_data,
    input  wire        tx_valid,
    output wire        tx_ready,
    output reg         tx_busy,
    output reg         tx_done,
    output reg         uart_txd
);

wire [31:0] baud_limit = (baud_div == 32'd0) ? 32'd1 : baud_div;
assign tx_ready = enable && !tx_busy;

reg [31:0] baud_cnt;
reg [3:0]  bit_cnt;
reg [7:0]  tx_data_r;

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        baud_cnt  <= 32'd0;
        bit_cnt   <= 4'd0;
        tx_data_r <= 8'd0;
        tx_busy   <= 1'b0;
        tx_done   <= 1'b0;
        uart_txd  <= 1'b1;
    end else begin
        tx_done <= 1'b0;

        if(!enable) begin
            baud_cnt <= 32'd0;
            bit_cnt  <= 4'd0;
            tx_busy  <= 1'b0;
            uart_txd <= 1'b1;
        end else if(!tx_busy) begin
            baud_cnt <= 32'd0;
            bit_cnt  <= 4'd0;
            uart_txd <= 1'b1;

            if(tx_valid) begin
                tx_data_r <= tx_data;
                tx_busy   <= 1'b1;
                uart_txd  <= 1'b0;
            end
        end else begin
            if(baud_cnt >= baud_limit - 32'd1) begin
                baud_cnt <= 32'd0;

                if(bit_cnt == 4'd9) begin
                    bit_cnt  <= 4'd0;
                    tx_busy  <= 1'b0;
                    tx_done  <= 1'b1;
                    uart_txd <= 1'b1;
                end else begin
                    bit_cnt <= bit_cnt + 4'd1;
                    case(bit_cnt + 4'd1)
                        4'd1: uart_txd <= tx_data_r[0];
                        4'd2: uart_txd <= tx_data_r[1];
                        4'd3: uart_txd <= tx_data_r[2];
                        4'd4: uart_txd <= tx_data_r[3];
                        4'd5: uart_txd <= tx_data_r[4];
                        4'd6: uart_txd <= tx_data_r[5];
                        4'd7: uart_txd <= tx_data_r[6];
                        4'd8: uart_txd <= tx_data_r[7];
                        default: uart_txd <= 1'b1;
                    endcase
                end
            end else begin
                baud_cnt <= baud_cnt + 32'd1;
            end
        end
    end
end

endmodule
