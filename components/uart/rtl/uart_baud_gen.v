//=============================================================================
// Module      : uart_baud_gen
// Description : Generate baud rate for uart
// EDITER      : MaoLvEr
//=============================================================================

module uart_baud_gen #(

    parameter SYS_CLK_HZ   = 108_000_000,   // System clock frequency in Hz
    parameter BAUD_RATE    = 115200,        // Target baud rate in bps
    parameter OVERSAMPLE   = 16             // Oversampling ratio
                                            //   1  -> single-rate (1 tick/bit)
                                            //   8  -> 8x oversampling
                                            //   16 -> 16x oversampling (standard)
) (

    input  wire clk,                        // System clock
    input  wire rst_n,                      // Asynchronous reset, active low
    output reg  baud_tick                   // Single-cycle pulse at
                                            //   BAUD_RATE * OVERSAMPLE Hz
);

    // Frequency division coefficient
    localparam integer DIVISOR = (SYS_CLK_HZ / (BAUD_RATE * OVERSAMPLE));
    // Indicates the bit width required for the fractional frequency coefficient
    localparam integer CNT_W   = $clog2(DIVISOR);

    reg [CNT_W-1:0] counter;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter   <= {CNT_W{1'b0}};
            baud_tick <= 1'b0;
        end
        // overflow
        else if (counter >= (DIVISOR - 1)) begin
            counter   <= {CNT_W{1'b0}};
            baud_tick <= 1'b1;
        end
        // normal
        else begin
            counter   <= counter + {{CNT_W-1{1'b0}}, 1'b1};
            baud_tick <= 1'b0;
        end
    end

endmodule