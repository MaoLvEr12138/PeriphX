module uart_core #(
    parameter integer DEFAULT_BAUD_DIV = 868
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    input  wire [31:0] baud_div,
    input  wire [7:0]  tx_data,
    input  wire        tx_valid,
    output wire        tx_ready,
    output wire        tx_busy,
    output wire        tx_done,
    output wire [7:0]  rx_data,
    output wire        rx_valid,
    output wire        rx_overrun,
    input  wire        rx_clear,
    input  wire        clear_tx_done,
    input  wire        clear_rx_overrun,
    input  wire        uart_rxd,
    output wire        uart_txd
);

localparam [31:0] DEFAULT_BAUD_DIV_VALUE = DEFAULT_BAUD_DIV;

wire [31:0] active_baud_div = (baud_div == 32'd0) ? DEFAULT_BAUD_DIV_VALUE : baud_div;
wire tx_done_pulse;
wire rx_overrun_raw;
reg  tx_done_sticky;
reg  rx_overrun_sticky;

assign tx_done = tx_done_sticky;
assign rx_overrun = rx_overrun_sticky;

uart_tx u_uart_tx (
    .clk      (clk),
    .rst_n    (rst_n),
    .enable   (enable),
    .baud_div (active_baud_div),
    .tx_data  (tx_data),
    .tx_valid (tx_valid),
    .tx_ready (tx_ready),
    .tx_busy  (tx_busy),
    .tx_done  (tx_done_pulse),
    .uart_txd (uart_txd)
);

uart_rx u_uart_rx (
    .clk          (clk),
    .rst_n        (rst_n),
    .enable       (enable),
    .baud_div     (active_baud_div),
    .uart_rxd     (uart_rxd),
    .rx_clear     (rx_clear),
    .clear_overrun(clear_rx_overrun),
    .rx_data      (rx_data),
    .rx_valid     (rx_valid),
    .rx_overrun   (rx_overrun_raw)
);

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        tx_done_sticky   <= 1'b0;
        rx_overrun_sticky <= 1'b0;
    end else begin
        if(clear_tx_done) begin
            tx_done_sticky <= 1'b0;
        end else if(tx_done_pulse) begin
            tx_done_sticky <= 1'b1;
        end

        if(clear_rx_overrun) begin
            rx_overrun_sticky <= 1'b0;
        end else if(rx_overrun_raw) begin
            rx_overrun_sticky <= 1'b1;
        end
    end
end

endmodule
