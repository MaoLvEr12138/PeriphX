module uart_core
#(
    parameter [31:0] DEFAULT_CONFIG = 32'h0003_01B2,
    parameter integer FIFO_ADDR_WIDTH = 4
)
(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        cfg_valid,
    input  wire [31:0] cfg_payload,
    output wire        cfg_bad_config,
    output wire        cfg_busy,
    input  wire        tx_write,
    input  wire [7:0]  tx_write_data,
    output wire        tx_full,
    output wire        tx_empty,
    output wire        tx_busy,
    input  wire        rx_read,
    output wire [7:0]  rx_read_data,
    output wire        rx_empty,
    output wire        rx_full,
    output wire [31:0] status,
    input  wire        uart_rxd,
    output wire        uart_txd
);

reg [15:0] baud_div_r;
reg [2:0]  data_bits_code_r;
reg [1:0]  parity_r;
reg        stop_bits_code_r;
reg        rx_overflow_seen;
reg        parity_error_seen;
reg        frame_error_seen;

wire [15:0] cfg_baud_div;
wire [2:0]  cfg_data_bits_code;
wire [1:0]  cfg_parity;
wire        cfg_stop_bits_code;
wire        cfg_reserved_nonzero;
wire        cfg_data_bits_invalid;
wire        cfg_parity_invalid;
wire        cfg_apply;
wire        fifo_flush;
wire        tx_fifo_read;
wire [7:0]  tx_fifo_data;
wire        tx_ready;
wire        tx_fifo_full;
wire        tx_fifo_empty;
wire        rx_fifo_full;
wire        rx_fifo_empty;
wire        rx_valid;
wire [7:0]  rx_data;
wire        rx_parity_error;
wire        rx_frame_error;
wire        rx_fifo_write;
wire        rx_overflow_event;
wire [FIFO_ADDR_WIDTH:0] unused_tx_count;
wire [FIFO_ADDR_WIDTH:0] unused_rx_count;

assign cfg_baud_div = cfg_payload[15:0];
assign cfg_data_bits_code = cfg_payload[18:16];
assign cfg_parity = cfg_payload[20:19];
assign cfg_stop_bits_code = cfg_payload[21];
assign cfg_reserved_nonzero = |cfg_payload[31:22];
assign cfg_data_bits_invalid = (cfg_data_bits_code > 3'd3);
assign cfg_parity_invalid = (cfg_parity == 2'd3);
assign cfg_bad_config = cfg_valid && (
    (cfg_baud_div == 16'd0) ||
    cfg_reserved_nonzero ||
    cfg_data_bits_invalid ||
    cfg_parity_invalid
);
assign cfg_busy = cfg_valid && tx_busy;
assign cfg_apply = cfg_valid && !cfg_bad_config && !cfg_busy;
assign fifo_flush = cfg_apply;
assign tx_fifo_read = !tx_fifo_empty && tx_ready;
assign rx_fifo_write = rx_valid && !rx_fifo_full;
assign rx_overflow_event = rx_valid && rx_fifo_full;
assign tx_full = tx_fifo_full;
assign tx_empty = tx_fifo_empty;
assign rx_full = rx_fifo_full;
assign rx_empty = rx_fifo_empty;
assign status = {
    24'd0,
    frame_error_seen,
    parity_error_seen,
    rx_overflow_seen,
    tx_busy,
    tx_fifo_full,
    tx_fifo_empty,
    rx_fifo_full,
    rx_fifo_empty
};

uart_fifo #(
    .DATA_WIDTH(8),
    .ADDR_WIDTH(FIFO_ADDR_WIDTH)
) u_tx_fifo (
    .clk       (clk),
    .rst_n     (rst_n),
    .flush     (fifo_flush),
    .wr_en     (tx_write),
    .wr_data   (tx_write_data),
    .full      (tx_fifo_full),
    .rd_en     (tx_fifo_read),
    .rd_data   (tx_fifo_data),
    .empty     (tx_fifo_empty),
    .used_count(unused_tx_count)
);

uart_fifo #(
    .DATA_WIDTH(8),
    .ADDR_WIDTH(FIFO_ADDR_WIDTH)
) u_rx_fifo (
    .clk       (clk),
    .rst_n     (rst_n),
    .flush     (fifo_flush),
    .wr_en     (rx_fifo_write),
    .wr_data   (rx_data),
    .full      (rx_fifo_full),
    .rd_en     (rx_read),
    .rd_data   (rx_read_data),
    .empty     (rx_fifo_empty),
    .used_count(unused_rx_count)
);

uart_tx u_uart_tx (
    .clk           (clk),
    .rst_n         (rst_n),
    .baud_div      (baud_div_r),
    .data_bits_code(data_bits_code_r),
    .parity        (parity_r),
    .stop_bits_code(stop_bits_code_r),
    .tx_valid      (tx_fifo_read),
    .tx_data       (tx_fifo_data),
    .tx_ready      (tx_ready),
    .tx_busy       (tx_busy),
    .uart_txd      (uart_txd)
);

uart_rx u_uart_rx (
    .clk           (clk),
    .rst_n         (rst_n),
    .baud_div      (baud_div_r),
    .data_bits_code(data_bits_code_r),
    .parity        (parity_r),
    .stop_bits_code(stop_bits_code_r),
    .uart_rxd      (uart_rxd),
    .rx_valid      (rx_valid),
    .rx_data       (rx_data),
    .parity_error  (rx_parity_error),
    .frame_error   (rx_frame_error)
);

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        baud_div_r <= DEFAULT_CONFIG[15:0];
        data_bits_code_r <= DEFAULT_CONFIG[18:16];
        parity_r <= DEFAULT_CONFIG[20:19];
        stop_bits_code_r <= DEFAULT_CONFIG[21];
        rx_overflow_seen <= 1'b0;
        parity_error_seen <= 1'b0;
        frame_error_seen <= 1'b0;
    end else begin
        if(cfg_apply) begin
            baud_div_r <= cfg_baud_div;
            data_bits_code_r <= cfg_data_bits_code;
            parity_r <= cfg_parity;
            stop_bits_code_r <= cfg_stop_bits_code;
            rx_overflow_seen <= 1'b0;
            parity_error_seen <= 1'b0;
            frame_error_seen <= 1'b0;
        end else begin
            if(rx_overflow_event) begin
                rx_overflow_seen <= 1'b1;
            end
            if(rx_parity_error) begin
                parity_error_seen <= 1'b1;
            end
            if(rx_frame_error) begin
                frame_error_seen <= 1'b1;
            end
        end
    end
end

endmodule
