module uart_top(
    input  wire sys_clk,
    input  wire sys_rst_n,
    input  wire uart_rxd,
    output wire uart_txd
);

wire [31:0] unused_status;
wire [7:0] unused_rx_data;

uart_core #(
    .DEFAULT_CONFIG(32'h0003_01B2),
    .FIFO_ADDR_WIDTH(4)
) u_uart_core (
    .clk           (sys_clk),
    .rst_n         (sys_rst_n),
    .cfg_valid     (1'b0),
    .cfg_payload   (32'd0),
    .cfg_bad_config(),
    .cfg_busy      (),
    .tx_write      (1'b0),
    .tx_write_data (8'd0),
    .tx_full       (),
    .tx_empty      (),
    .tx_busy       (),
    .rx_read       (1'b0),
    .rx_read_data  (unused_rx_data),
    .rx_empty      (),
    .rx_full       (),
    .status        (unused_status),
    .uart_rxd      (uart_rxd),
    .uart_txd      (uart_txd)
);

endmodule
