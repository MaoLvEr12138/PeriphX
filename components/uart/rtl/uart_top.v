module uart_top(
    input  wire sys_clk,
    input  wire sys_rst_n,
    input  wire uart_rxd,
    output wire uart_txd
);

parameter UART_BPS = 57600;
parameter CLK_FREQ = 50_000_000;
localparam integer DEFAULT_BAUD_DIV = CLK_FREQ / UART_BPS;
localparam [31:0] DEFAULT_BAUD_DIV_VALUE = DEFAULT_BAUD_DIV;

wire        tx_ready;
wire        tx_busy;
wire        tx_done;
wire [7:0]  rx_data;
wire        rx_valid;
wire        rx_overrun;

uart_core #(
    .DEFAULT_BAUD_DIV(DEFAULT_BAUD_DIV)
) u_uart_core (
    .clk              (sys_clk),
    .rst_n            (sys_rst_n),
    .enable           (1'b1),
    .baud_div         (DEFAULT_BAUD_DIV_VALUE),
    .tx_data          (8'd0),
    .tx_valid         (1'b0),
    .tx_ready         (tx_ready),
    .tx_busy          (tx_busy),
    .tx_done          (tx_done),
    .rx_data          (rx_data),
    .rx_valid         (rx_valid),
    .rx_overrun       (rx_overrun),
    .rx_clear         (1'b0),
    .clear_tx_done    (1'b0),
    .clear_rx_overrun (1'b0),
    .uart_rxd         (uart_rxd),
    .uart_txd         (uart_txd)
);

endmodule
