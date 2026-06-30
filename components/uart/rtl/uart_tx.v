//=============================================================================
// Module      : uart_tx
// Description : UART transmitter with ready/valid handshake.
//               Supports 5-8 data bits, 1-2 stop bits,
//               and NONE / ODD / EVEN parity.
// Language    : Verilog-2001 (IEEE 1364-2001)
// Platform    : Vendor independent, pure synthesizable RTL
//=============================================================================

module uart_tx #(
    //-------------------------------------------------------------------------
    // Parameters
    //-------------------------------------------------------------------------
    parameter DATA_W    = 8,                // Data bits: 5, 6, 7, or 8
    parameter STOP_BITS = 1,                // Stop bits: 1 or 2
    parameter PARITY    = 0                 // 0 = NONE, 1 = ODD, 2 = EVEN
) (
    //-------------------------------------------------------------------------
    // I/O Ports
    //-------------------------------------------------------------------------
    input  wire             clk,            // System clock
    input  wire             rst_n,          // Asynchronous reset, active low
    input  wire             baud_tick_in,   // Tick pulse from uart_baud_gen
                                            //   Period = 1 / (BAUD_RATE * OVERSAMPLE)
                                            //   For OVERSAMPLE=1, one tick per bit.
                                            //   For OVERSAMPLE=16, the caller should
                                            //   use baud_tick_in as the bit clock.
    input  wire             tx_valid,       // Upstream data valid
    output reg              tx_ready,       // Transmitter ready to accept
    input  wire [DATA_W-1:0] tx_data,      // Parallel data to transmit
    output reg              tx_line         // UART serial output line
);

    //==========================================================================
    // Local Parameters
    //==========================================================================

    // Parity mask width matches data width
    localparam PARITY_NONE = 2'd0;
    localparam PARITY_ODD  = 2'd1;
    localparam PARITY_EVEN = 2'd2;

    // Number of bits in a full frame (max)
    // Start(1) + Data(DATA_W) + Parity(0/1) + Stop(STOP_BITS)
    localparam BIT_COUNT_W = $clog2(1 + DATA_W + 1 + 2);

    //==========================================================================
    // State Machine Encoding
    //==========================================================================
    localparam S_IDLE      = 3'd0;
    localparam S_START     = 3'd1;
    localparam S_DATA      = 3'd2;
    localparam S_PARITY    = 3'd3;
    localparam S_STOP      = 3'd4;

    //==========================================================================
    // Internal Registers
    //==========================================================================
    reg  [2:0]               state;
    reg  [2:0]               next_state;

    reg  [DATA_W-1:0]        shift_reg;     // Data shift register
    reg  [BIT_COUNT_W-1:0]   bit_cnt;       // Bit counter within DATA phase
    reg                      parity_bit;    // Computed parity bit

    //==========================================================================
    // State Machine: Sequential (Current State)
    //==========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            tx_line  <= 1'b1;               // Idle line is high
            tx_ready <= 1'b1;               // Ready in idle
            shift_reg  <= {DATA_W{1'b0}};
            bit_cnt    <= {BIT_COUNT_W{1'b0}};
            parity_bit <= 1'b0;
        end
        else begin
            state <= next_state;

            case (state)
                S_IDLE: begin
                    tx_line  <= 1'b1;
                    tx_ready <= 1'b1;
                    if (tx_valid) begin
                        // Load shift register on acceptance
                        shift_reg  <= tx_data;
                        bit_cnt    <= {BIT_COUNT_W{1'b0}};
                        // Pre-compute parity (odd parity = XOR of all data bits)
                        // For even parity, invert the odd result
                        parity_bit <= (PARITY == PARITY_ODD)
                                      ? ~(^tx_data)
                                      : (PARITY == PARITY_EVEN)
                                        ? (^tx_data)
                                        : 1'b0;
                    end
                end

                S_START: begin
                    tx_line  <= 1'b0;       // Start bit = low
                    tx_ready <= 1'b0;
                end

                S_DATA: begin
                    tx_ready <= 1'b0;
                    if (baud_tick_in) begin
                        // LSB first
                        tx_line   <= shift_reg[0];
                        shift_reg <= {1'b0, shift_reg[DATA_W-1:1]};
                        bit_cnt   <= bit_cnt + {{BIT_COUNT_W-1{1'b0}}, 1'b1};
                    end
                end

                S_PARITY: begin
                    tx_ready <= 1'b0;
                    tx_line  <= parity_bit;
                end

                S_STOP: begin
                    tx_ready <= (baud_tick_in && (bit_cnt >= STOP_BITS));
                    tx_line  <= 1'b1;       // Stop bit = high
                    if (baud_tick_in) begin
                        bit_cnt <= bit_cnt + {{BIT_COUNT_W-1{1'b0}}, 1'b1};
                    end
                end

                default: begin
                    tx_line  <= 1'b1;
                    tx_ready <= 1'b1;
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
                if (tx_valid) begin
                    next_state = S_START;
                end
            end

            S_START: begin
                if (baud_tick_in) begin
                    next_state = S_DATA;
                end
            end

            S_DATA: begin
                if (baud_tick_in && (bit_cnt >= (DATA_W - 1))) begin
                    if (PARITY != PARITY_NONE) begin
                        next_state = S_PARITY;
                    end
                    else begin
                        next_state  = S_STOP;
                    end
                end
            end

            S_PARITY: begin
                if (baud_tick_in) begin
                    next_state = S_STOP;
                end
            end

            S_STOP: begin
                if (baud_tick_in && (bit_cnt >= STOP_BITS)) begin
                    next_state = S_IDLE;
                end
            end

            default: begin
                next_state = S_IDLE;
            end
        endcase
    end

endmodule