module uart_rx(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    input  wire [31:0] baud_div,
    input  wire        uart_rxd,
    input  wire        rx_clear,
    input  wire        clear_overrun,
    output reg  [7:0]  rx_data,
    output reg         rx_valid,
    output reg         rx_overrun
);

localparam [1:0] RX_IDLE  = 2'd0;
localparam [1:0] RX_START = 2'd1;
localparam [1:0] RX_DATA  = 2'd2;
localparam [1:0] RX_STOP  = 2'd3;

wire [31:0] baud_limit = (baud_div == 32'd0) ? 32'd1 : baud_div;
wire [31:0] half_baud_limit = (baud_limit > 32'd1) ? (baud_limit >> 1) : 32'd1;

reg [1:0]  state;
reg [31:0] baud_cnt;
reg [2:0]  bit_cnt;
reg [7:0]  rx_shift;
reg        rxd_d0;
reg        rxd_d1;

wire rxd_falling = rxd_d1 && !rxd_d0;

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        rxd_d0 <= 1'b1;
        rxd_d1 <= 1'b1;
    end else begin
        rxd_d0 <= uart_rxd;
        rxd_d1 <= rxd_d0;
    end
end

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        state      <= RX_IDLE;
        baud_cnt   <= 32'd0;
        bit_cnt    <= 3'd0;
        rx_shift   <= 8'd0;
        rx_data    <= 8'd0;
        rx_valid   <= 1'b0;
        rx_overrun <= 1'b0;
    end else begin
        if(rx_clear) begin
            rx_valid <= 1'b0;
        end

        if(clear_overrun) begin
            rx_overrun <= 1'b0;
        end

        if(!enable) begin
            state    <= RX_IDLE;
            baud_cnt <= 32'd0;
            bit_cnt  <= 3'd0;
        end else begin
            case(state)
                RX_IDLE: begin
                    baud_cnt <= 32'd0;
                    bit_cnt  <= 3'd0;
                    if(rxd_falling) begin
                        state <= RX_START;
                    end
                end

                RX_START: begin
                    if(baud_cnt >= half_baud_limit - 32'd1) begin
                        baud_cnt <= 32'd0;
                        if(!rxd_d1) begin
                            state <= RX_DATA;
                        end else begin
                            state <= RX_IDLE;
                        end
                    end else begin
                        baud_cnt <= baud_cnt + 32'd1;
                    end
                end

                RX_DATA: begin
                    if(baud_cnt >= baud_limit - 32'd1) begin
                        baud_cnt <= 32'd0;
                        rx_shift[bit_cnt] <= rxd_d1;
                        if(bit_cnt == 3'd7) begin
                            bit_cnt <= 3'd0;
                            state   <= RX_STOP;
                        end else begin
                            bit_cnt <= bit_cnt + 3'd1;
                        end
                    end else begin
                        baud_cnt <= baud_cnt + 32'd1;
                    end
                end

                RX_STOP: begin
                    if(baud_cnt >= baud_limit - 32'd1) begin
                        baud_cnt <= 32'd0;
                        state    <= RX_IDLE;
                        if(rx_valid) begin
                            rx_overrun <= 1'b1;
                        end else begin
                            rx_data  <= rx_shift;
                            rx_valid <= 1'b1;
                        end
                    end else begin
                        baud_cnt <= baud_cnt + 32'd1;
                    end
                end

                default: begin
                    state <= RX_IDLE;
                end
            endcase
        end
    end
end

endmodule
