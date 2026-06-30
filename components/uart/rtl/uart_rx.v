//=============================================================================
// Module      : uart_rx
// Description : UART receiver with 16x oversampling, ready/valid handshake.
//               Supports 5-8 data bits, 1-2 stop bits,
//               and NONE / ODD / EVEN parity with error detection.
//               Input baud_tick_in is expected at 16x baud rate (default).
// Language    : Verilog-2001 (IEEE 1364-2001)
// Platform    : Vendor independent, pure synthesizable RTL
//=============================================================================

module uart_rx #(
    //-------------------------------------------------------------------------
    // Parameters
    //-------------------------------------------------------------------------
    parameter DATA_W    = 8,                // Data bits: 5, 6, 7, or 8
    parameter STOP_BITS = 1,                // Stop bits: 1 or 2
    parameter PARITY    = 0,                // 0 = NONE, 1 = ODD, 2 = EVEN
    parameter OVERSAMPLE = 16               // Oversampling ratio (default 16x)
                                            //   Must match uart_baud_gen setting
) (
    //-------------------------------------------------------------------------
    // I/O Ports
    //-------------------------------------------------------------------------
    input  wire             clk,            // System clock
    input  wire             rst_n,          // Asynchronous reset, active low
    input  wire             baud_tick_in,   // Tick pulse from uart_baud_gen
                                            //   Must be BAUD_RATE * OVERSAMPLE Hz
    input  wire             rx_line,        // UART serial input line
    output reg  [DATA_W-1:0] rx_data,      // Received parallel data
    output reg              rx_valid,       // Single-cycle pulse when frame complete
    output reg              rx_error        // Error flag: parity error or framing error
);

    //==========================================================================
    // Local Parameters
    //==========================================================================
    localparam PARITY_NONE = 2'd0;
    localparam PARITY_ODD  = 2'd1;
    localparam PARITY_EVEN = 2'd2;

    // Sample point = OVERSAMPLE / 2 (e.g., 8 for 16x oversampling)
    // This is the center of each bit period.
    localparam SAMPLE_POINT = (OVERSAMPLE / 2);

    // Bit width for tick counter (0 to OVERSAMPLE-1)
    localparam TICK_CNT_W = $clog2(OVERSAMPLE);

    // Bit width for data bit counter
    localparam DATA_CNT_W = $clog2(DATA_W);

    //==========================================================================
    // State Machine Encoding
    //==========================================================================
    localparam S_IDLE       = 3'd0;
    localparam S_START      = 3'd1;
    localparam S_START_CHK  = 3'd2;
    localparam S_DATA       = 3'd3;
    localparam S_PARITY     = 3'd4;
    localparam S_STOP       = 3'd5;
    localparam S_DONE       = 3'd6;

    //==========================================================================
    // Internal Registers
    //==========================================================================
    reg  [2:0]                   state;
    reg  [2:0]                   next_state;

    reg  [TICK_CNT_W-1:0]        tick_cnt;    // Tick counter (0 to OVERSAMPLE-1)
    reg  [DATA_CNT_W-1:0]        data_cnt;     // Data bit counter
    reg  [DATA_W-1:0]            shift_reg;    // Data shift register
    reg                          parity_calc;  // Calculated parity for comparison
    reg                          parity_err;   // Parity error flag
    reg                          frame_err;    // Framing error flag

    //==========================================================================
    // State Machine: Sequential (Current State)
    //==========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= S_IDLE;
            tick_cnt    <= {TICK_CNT_W{1'b0}};
            data_cnt    <= {DATA_CNT_W{1'b0}};
            shift_reg   <= {DATA_W{1'b0}};
            parity_calc <= 1'b0;
            parity_err  <= 1'b0;
            frame_err   <= 1'b0;
            rx_data     <= {DATA_W{1'b0}};
            rx_valid    <= 1'b0;
            rx_error    <= 1'b0;
        end
        else begin
            state <= next_state;

            case (state)
                S_IDLE: begin
                    tick_cnt    <= {TICK_CNT_W{1'b0}};
                    data_cnt    <= {DATA_CNT_W{1'b0}};
                    shift_reg   <= {DATA_W{1'b0}};
                    parity_calc <= 1'b0;
                    parity_err  <= 1'b0;
                    frame_err   <= 1'b0;
                    rx_valid    <= 1'b0;
                    rx_error    <= 1'b0;
                    // rx_data retains last received byte
                end

                S_START: begin
                    // Wait until the center of the start bit
                    if (baud_tick_in) begin
                        tick_cnt <= tick_cnt + {{TICK_CNT_W-1{1'b0}}, 1'b1};
                    end
                end

                S_START_CHK: begin
                    // Confirm start bit is still low at center
                    tick_cnt <= {TICK_CNT_W{1'b0}};
                end

                S_DATA: begin
                    if (baud_tick_in) begin
                        tick_cnt <= tick_cnt + {{TICK_CNT_W-1{1'b0}}, 1'b1};
                        // At the center of each bit, sample rx_line
                        if (tick_cnt == (SAMPLE_POINT - 1)) begin
                            // LSB received first
                            shift_reg <= {rx_line, shift_reg[DATA_W-1:1]};
                            // Accumulate parity (XOR each received bit)
                            parity_calc <= parity_calc ^ rx_line;
                            data_cnt    <= data_cnt + {{DATA_CNT_W-1{1'b0}}, 1'b1};
                        end
                    end
                end

                S_PARITY: begin
                    if (baud_tick_in && (tick_cnt == (SAMPLE_POINT - 1))) begin
                        // Compare received parity bit with calculated
                        if (PARITY == PARITY_ODD) begin
                            // Odd parity: XOR of all bits + parity bit should be 1
                            parity_err <= (parity_calc ^ rx_line) ? 1'b0 : 1'b1;
                        end
                        else if (PARITY == PARITY_EVEN) begin
                            // Even parity: XOR of all bits + parity bit should be 0
                            parity_err <= (parity_calc ^ rx_line) ? 1'b1 : 1'b0;
                        end
                        tick_cnt <= {TICK_CNT_W{1'b0}};
                    end
                    else if (baud_tick_in) begin
                        tick_cnt <= tick_cnt + {{TICK_CNT_W-1{1'b0}}, 1'b1};
                    end
                end

                S_STOP: begin
                    if (baud_tick_in && (tick_cnt == (SAMPLE_POINT - 1))) begin
                        // Stop bit must be high
                        if (rx_line != 1'b1) begin
                            frame_err <= 1'b1;
                        end
                        tick_cnt <= tick_cnt + {{TICK_CNT_W-1{1'b0}}, 1'b1};
                    end
                    else if (baud_tick_in && tick_cnt >= (OVERSAMPLE - 1)) begin
                        tick_cnt <= {TICK_CNT_W{1'b0}};
                    end
                    else if (baud_tick_in) begin
                        tick_cnt <= tick_cnt + {{TICK_CNT_W-1{1'b0}}, 1'b1};
                    end
                end

                S_DONE: begin
                    // Output the received byte
                    rx_data  <= shift_reg;
                    rx_valid <= 1'b1;
                    rx_error <= parity_err | frame_err;
                end

                default: begin
                    state <= S_IDLE;
                end
            endcase
        end
    end

    //==========================================================================
    // State Machine: Combinational (Next State)
    //==========================================================================
    always @(*) begin
        next_state = state;

        case (state)
            S_IDLE: begin
                // Detect falling edge (start bit)
                if (!rx_line) begin
                    next_state = S_START;
                end
            end

            S_START: begin
                // Wait until center of start bit
                if (baud_tick_in && (tick_cnt >= (SAMPLE_POINT - 1))) begin
                    next_state = S_START_CHK;
                end
            end

            S_START_CHK: begin
                if (rx_line == 1'b1) begin
                    // False start, return to idle
                    next_state = S_IDLE;
                end
                else begin
                    // Genuine start bit, begin data reception
                    next_state = S_DATA;
                end
            end

            S_DATA: begin
                if (baud_tick_in
                    && (tick_cnt >= (OVERSAMPLE - 1))
                    && (data_cnt >= (DATA_W - 1))) begin
                    if (PARITY != PARITY_NONE) begin
                        next_state = S_PARITY;
                    end
                    else begin
                        next_state = S_STOP;
                    end
                end
            end

            S_PARITY: begin
                if (baud_tick_in && (tick_cnt >= (OVERSAMPLE - 1))) begin
                    next_state = S_STOP;
                end
            end

            S_STOP: begin
                if (baud_tick_in && (tick_cnt >= (OVERSAMPLE - 1))
                    && (data_cnt >= (DATA_W - 1 + STOP_BITS))) begin
                    next_state = S_DONE;
                end
            end

            S_DONE: begin
                // Automatically return to IDLE for next frame
                next_state = S_IDLE;
            end

            default: begin
                next_state = S_IDLE;
            end
        endcase
    end

endmodule