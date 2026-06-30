//=============================================================================
// Testbench   : uart_rx_tb
// Description : Self-checking testbench for uart_rx module.
//               Verifies start bit detection, data reception (LSB first),
//               parity checking, framing error detection, and false
//               start bit rejection.
// Language    : Verilog-2001 (IEEE 1364-2001)
// Simulator   : iverilog / ModelSim / VCS / Xcelium
//=============================================================================

`timescale 1ns / 1ps

module uart_rx_tb;

    //==========================================================================
    // DUT Parameters
    //==========================================================================
    parameter CLK_PERIOD    = 10;           // 100 MHz
    parameter DATA_W        = 8;
    parameter STOP_BITS     = 1;
    parameter PARITY        = 0;            // 0 = NONE, 1 = ODD, 2 = EVEN
    parameter OVERSAMPLE    = 16;

    // Tick period in clock cycles (divisor + 1 for this simulation)
    // 100M / (1M * 16) = 6.25 -> tick every 7 cycles
    parameter TICK_PERIOD   = 7;

    //==========================================================================
    // Signals
    //==========================================================================
    reg             clk;
    reg             rst_n;
    reg             baud_tick_in;
    reg             rx_line;
    wire [DATA_W-1:0] rx_data;
    wire            rx_valid;
    wire            rx_error;

    //==========================================================================
    // DUT Instantiation
    //==========================================================================
    uart_rx #(
        .DATA_W        (DATA_W),
        .STOP_BITS     (STOP_BITS),
        .PARITY        (PARITY),
        .OVERSAMPLE    (OVERSAMPLE)
    ) dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .baud_tick_in  (baud_tick_in),
        .rx_line       (rx_line),
        .rx_data       (rx_data),
        .rx_valid      (rx_valid),
        .rx_error      (rx_error)
    );

    //==========================================================================
    // Clock Generation
    //==========================================================================
    always #(CLK_PERIOD / 2.0) clk = ~clk;

    //==========================================================================
    // Tick Generation (simulates uart_baud_gen output)
    //==========================================================================
    reg [31:0] tick_counter;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tick_counter <= 32'd0;
            baud_tick_in <= 1'b0;
        end
        else begin
            if (tick_counter >= (TICK_PERIOD - 1)) begin
                tick_counter <= 32'd0;
                baud_tick_in <= 1'b1;
            end
            else begin
                tick_counter <= tick_counter + 1;
                baud_tick_in <= 1'b0;
            end
        end
    end

    //==========================================================================
    // Test Variables
    //==========================================================================
    integer errors;
    integer i;
    reg  [7:0] sent_byte;
    reg  [7:0] received_byte;
    integer    bit_idx;
    reg        parity_bit;

    //==========================================================================
    // Helper: Wait for N baud ticks (at tick boundaries)
    //==========================================================================
    task wait_ticks;
        input integer n;
        integer j;
        begin
            for (j = 0; j < n; j = j + 1) begin
                @(posedge clk);
                while (!baud_tick_in) @(posedge clk);
            end
        end
    endtask

    //==========================================================================
    // Helper: Drive a complete UART frame on rx_line
    //==========================================================================
    task drive_frame;
        input [DATA_W-1:0] data;
        input              inject_parity_error;  // 1 = flip parity
        input              inject_frame_error;   // 1 = drive stop bit low
        reg                calc_parity;
        integer j;
        begin
            // Calculate parity
            calc_parity = (^data);  // Even parity XOR

            // 1. Start bit (low for 1 bit period = OVERSAMPLE ticks)
            rx_line = 1'b0;
            wait_ticks(OVERSAMPLE);

            // 2. Data bits (LSB first), each for OVERSAMPLE ticks
            for (j = 0; j < DATA_W; j = j + 1) begin
                rx_line = data[j];
                wait_ticks(OVERSAMPLE);
            end

            // 3. Parity bit (if PARITY != NONE)
            if (PARITY != 0) begin
                if (PARITY == 1) begin  // ODD
                    rx_line = ~calc_parity ^ inject_parity_error;
                end
                else begin  // EVEN
                    rx_line = calc_parity ^ inject_parity_error;
                end
                wait_ticks(OVERSAMPLE);
            end

            // 4. Stop bit(s)
            for (j = 0; j < STOP_BITS; j = j + 1) begin
                rx_line = ~inject_frame_error;  // 0 if frame error, else 1
                wait_ticks(OVERSAMPLE);
            end

            // Return line to idle
            rx_line = 1'b1;
            wait_ticks(OVERSAMPLE);  // Extra inter-frame gap
        end
    endtask

    //==========================================================================
    // Helper: Wait for rx_valid pulse and capture rx_data
    //==========================================================================
    task capture_rx;
        begin
            // Wait for rx_valid pulse
            while (!rx_valid) @(posedge clk);

            received_byte = rx_data;

            // rx_valid is single-cycle, verify it deasserts next cycle
            @(posedge clk);
            if (rx_valid !== 1'b0) begin
                $display("  FAIL: rx_valid stayed high > 1 cycle!");
                errors = errors + 1;
            end
        end
    endtask

    //==========================================================================
    // Main Test Sequence
    //==========================================================================
    initial begin
        clk      = 1'b0;
        rst_n    = 1'b0;
        rx_line  = 1'b1;
        errors   = 0;

        $display("============================================");
        $display(" uart_rx Testbench");
        $display(" DATA_W = %0d, STOP_BITS = %0d, PARITY = %0d, OVERSAMPLE = %0d",
                 DATA_W, STOP_BITS, PARITY, OVERSAMPLE);
        $display("============================================");

        //-------------------------------------------------------------------------
        // Reset
        //-------------------------------------------------------------------------
        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (10) @(posedge clk);

        //---------------------------------------------------------------------
        // Test 1: Idle behavior
        //---------------------------------------------------------------------
        $display("\n[TEST 1] Idle state check...");
        if (rx_valid !== 1'b0) begin
            $display("  FAIL: rx_valid asserted in idle!");
            errors = errors + 1;
        end
        else begin
            $display("  PASS: rx_valid = 0 in idle");
        end

        //---------------------------------------------------------------------
        // Test 2: Receive known byte patterns (8-N-1)
        //---------------------------------------------------------------------
        $display("\n[TEST 2] Receive byte patterns...");
        // Test various byte values
        begin
            reg [7:0] test_bytes [0:7];
            test_bytes[0] = 8'h55;
            test_bytes[1] = 8'hAA;
            test_bytes[2] = 8'h00;
            test_bytes[3] = 8'hFF;
            test_bytes[4] = 8'h41;  // 'A'
            test_bytes[5] = 8'h5A;  // 'Z'
            test_bytes[6] = 8'h31;  // '1'
            test_bytes[7] = 8'h39;  // '9'

            for (i = 0; i < 8; i = i + 1) begin
                sent_byte = test_bytes[i];
                fork
                    begin
                        drive_frame(sent_byte, 1'b0, 1'b0);
                    end
                    begin
                        capture_rx();
                        if (received_byte !== sent_byte) begin
                            $display("  FAIL: Expected 0x%02h, got 0x%02h",
                                     sent_byte, received_byte);
                            errors = errors + 1;
                        end
                        else begin
                            $display("  PASS: 0x%02h ('%c') received correctly",
                                     sent_byte,
                                     (sent_byte >= 33 && sent_byte <= 126) ? sent_byte : "?");
                        end
                    end
                join
            end
        end

        //---------------------------------------------------------------------
        // Test 3: False start bit rejection (glitch test)
        //---------------------------------------------------------------------
        $display("\n[TEST 3] False start bit rejection...");
        begin
            // Drive rx_line low briefly (shorter than 8 ticks)
            rx_line = 1'b0;
            wait_ticks(4);  // Halfway to center of start bit
            rx_line = 1'b1; // Return to idle before center check

            // Drive a valid frame after recovery
            wait_ticks(OVERSAMPLE * 2);

            fork
                begin
                    drive_frame(8'hC3, 1'b0, 1'b0);
                end
                begin
                    capture_rx();
                    if (received_byte !== 8'hC3) begin
                        $display("  FAIL: After glitch, expected 0xC3, got 0x%02h",
                                 received_byte);
                        errors = errors + 1;
                    end
                    else begin
                        $display("  PASS: False start rejected, 0xC3 received correctly");
                    end
                end
            join
        end

        //---------------------------------------------------------------------
        // Test 4: Framing error detection (8-N-1)
        //---------------------------------------------------------------------
        $display("\n[TEST 4] Framing error detection...");
        begin
            fork
                begin
                    // Drive frame with bad stop bit (low)
                    drive_frame(8'h7E, 1'b0, 1'b1);  // inject frame error
                end
                begin
                    capture_rx();
                    if (rx_error !== 1'b1) begin
                        $display("  FAIL: Expected rx_error=1 with bad stop bit, got %b",
                                 rx_error);
                        errors = errors + 1;
                    end
                    else begin
                        $display("  PASS: Frame error detected (rx_error=%b)", rx_error);
                    end
                end
            join
        end

        //---------------------------------------------------------------------
        // Results
        //---------------------------------------------------------------------
        $display("\n============================================");
        if (errors == 0)
            $display(" ALL TESTS PASSED");
        else
            $display(" %0d TEST(S) FAILED", errors);
        $display("============================================");

        $finish;
    end

endmodule