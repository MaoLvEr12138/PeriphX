//=============================================================================
// Module      : uart_top
// Description : Top-level UART module integrating baud generator,
//               transmitter, and receiver.  Designed for direct instantiation
//               by the PeriphX Python generator.
// Language    : Verilog-2001 (IEEE 1364-2001)
// Platform    : Vendor independent, pure synthesizable RTL
//=============================================================================

module uart_top #(
    //-------------------------------------------------------------------------
    // System Parameters
    //-------------------------------------------------------------------------
    parameter SYS_CLK_HZ   = 108_000_000,   // System clock frequency in Hz
    parameter BAUD_RATE    = 115200,        // Baud rate in bps

    //-------------------------------------------------------------------------
    // Frame Parameters
    //-------------------------------------------------------------------------
    parameter DATA_W       = 8,             // Data bits: 5-8
    parameter STOP_BITS    = 1,             // Stop bits: 1 or 2
    parameter PARITY       = 0,             // 0 = NONE, 1 = ODD, 2 = EVEN

    //-------------------------------------------------------------------------
    // Oversampling Parameters
    //-------------------------------------------------------------------------
    parameter OVERSAMPLE   = 16             // RX oversampling ratio (16x standard)
                                            //   1  = single-rate TX, no oversample RX
                                            //   8  = 8x oversampling
                                            //   16 = 16x oversampling (recommended)
) (
    //-------------------------------------------------------------------------
    // Clock & Reset
    //-------------------------------------------------------------------------
    input  wire             clk,
    input  wire             rst_n,

    //-------------------------------------------------------------------------
    // UART Transmit Interface
    //-------------------------------------------------------------------------
    input  wire             tx_valid,
    output wire             tx_ready,
    input  wire [DATA_W-1:0] tx_data,
    output wire             tx_line,

    //-------------------------------------------------------------------------
    // UART Receive Interface
    //-------------------------------------------------------------------------
    input  wire             rx_line,
    output wire [DATA_W-1:0] rx_data,
    output wire             rx_valid,
    output wire             rx_error
);

    //==========================================================================
    // Internal Nets
    //==========================================================================
    wire baud_tick;

    //==========================================================================
    // Baud Rate Generator
    //==========================================================================
    uart_baud_gen #(
        .SYS_CLK_HZ    (SYS_CLK_HZ),
        .BAUD_RATE     (BAUD_RATE),
        .OVERSAMPLE    (OVERSAMPLE)
    ) u_baud_gen (
        .clk           (clk),
        .rst_n         (rst_n),
        .baud_tick     (baud_tick)
    );

    //==========================================================================
    // UART Transmitter
    //==========================================================================
    uart_tx #(
        .DATA_W        (DATA_W),
        .STOP_BITS     (STOP_BITS),
        .PARITY        (PARITY)
    ) u_tx (
        .clk           (clk),
        .rst_n         (rst_n),
        .baud_tick_in  (baud_tick),
        .tx_valid      (tx_valid),
        .tx_ready      (tx_ready),
        .tx_data       (tx_data),
        .tx_line       (tx_line)
    );

    //==========================================================================
    // UART Receiver
    //==========================================================================
    uart_rx #(
        .DATA_W        (DATA_W),
        .STOP_BITS     (STOP_BITS),
        .PARITY        (PARITY),
        .OVERSAMPLE    (OVERSAMPLE)
    ) u_rx (
        .clk           (clk),
        .rst_n         (rst_n),
        .baud_tick_in  (baud_tick),
        .rx_line       (rx_line),
        .rx_data       (rx_data),
        .rx_valid      (rx_valid),
        .rx_error      (rx_error)
    );

endmodule