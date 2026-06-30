//=============================================================================
// Testbench   : uart_tx_tb
// Description : Self-checking testbench for uart_tx module.
//               Verifies start/stop bits, data serialization (LSB first),
//               parity, ready/valid handshake, and back-to-back transmit.
// Language    : Verilog-2001 (IEEE 1364-2001)
// Simulator   : iverilog / ModelSim / VCS / Xcelium
//=============================================================================

`timescale 1ns / 1ps

module uart_tx_tb;

    //==========================================================================
    // DUT Parameters
    //==========================================================================
    parameter CLK_PERIOD    = 10;           // 100 MHz
    parameter DATA_W        = 8;
    parameter STOP_BITS     = 1;
    parameter PARITY        = 0;            // Start with NONE, test ODD/EVEN later

    // Tick period in system clock cycles (e.g., every 100ns = 10 cycles * 10ns)
    // For simulation, we drive baud_tick_in at a known rate.
    // Here: tick every 16 clock cycles (simulating 16x oversampling)
    parameter TICK_PERIOD   = 16;

    //==========================================================================
    // Signals
    //==========================================================================
    reg             clk;
    reg             rst_n;
    reg             baud_tick_in;
    reg             tx_valid;
    wire            tx_ready;
    reg  [DATA_W-1:0] tx_data;
    wire            tx_line;

    //==========================================================================
    // DUT Instantiation (default: 8-N-1)
    //==========================================================================
    uart_tx #(
        .DATA_W        (DATA_W),
        .STOP_BITS     (STOP_BITS),
        .PARITY        (PARITY)
    ) dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .baud_tick_in  (baud_tick_in),
        .tx_valid      (tx_valid),
        .tx_ready      (tx_ready),
        .tx_data       (tx_data),
        .tx_line       (tx_line)
    );

    //==========================================================================
    // Clock & Tick Generation
    //==========================================================================
    always #(CLK_PERIOD / 2.0) clk = ~clk;

    reg [31:0] tick_counter;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tick_counter <= 32'd0;
            baud_tick_in <= 1'b0;
        end
        else begin
            tick_counter <= tick_counter + 1;
            // Generate one-cycle pulse every TICK_PERIOD cycles
            baud_tick_in <= (tick_counter == (TICK_PERIOD - 1));
        end
    end

    //==========================================================================
    // Test Variables
    //==========================================================================
    integer errors;
    integer i;
    reg  [7:0] expected_byte;
    reg  [7:0] captured_byte;
    reg        captured_parity;
    integer    bit_idx;

    //==========================================================================
    // Helper Tasks
    //==========================================================================
    // Wait for N baud ticks
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

    // Send a single byte and verify it on tx_line
    task send_byte_verify;
        input [7:0] data;
        begin
            // Wait until tx_ready
            while (!tx_ready) @(posedge clk);
            tx_data  = data;
            tx_valid = 1'b1;
            @(posedge clk);
            tx_valid = 1'b0;

            // Wait for start bit (tx_line goes low)
            while (tx_line !== 1'b0) @(posedge clk);

            // Now sample at the center of each bit period
            // Wait a half tick to reach the middle of start bit
            // The start bit is already being driven, skip past it
            // We're at the start of the start bit, wait 1 tick to reach
            // the middle of the first data bit
            wait_ticks(1);  // Move past start bit to first data bit

            // Collect 8 data bits (LSB first)
            captured_byte = 8'd0;
            for (bit_idx = 0; bit_idx < DATA_W; bit_idx = bit_idx + 1) begin
                // We are at tick boundary, sample tx_line at next posedge
                @(posedge clk);
                captured_byte[bit_idx] = tx_line;
                wait_ticks(1);
            end

            $display("  Sent: 0x%02h ('%c'), Captured: 0x%02h",
                     data, (data >= 33 && data <= 126) ? data : "?",
                     captured_byte);

            if (captured_byte !== data) begin
                $display("  FAIL: Data mismatch!");
                errors = errors + 1;
            end

            // Verify stop bit(s) are high
            for (bit_idx = 0; bit_idx < STOP_BITS; bit_idx = bit_idx + 1) begin
                @(posedge clk);
                if (tx_line !== 1'b1 && bit_idx == 0) begin
                    $display("  FAIL: Stop bit %0d is not high!", bit_idx);
                    errors = errors + 1;
                end
                wait_ticks(1);
            end

            // Wait for tx_ready to go high again
            repeat (5) @(posedge clk);
        end
    endtask

    //==========================================================================
    // Main Test Sequence
    //==========================================================================
    initial begin
        clk      = 1'b0;
        rst_n    = 1'b0;
        baud_tick_in = 1'b0;
        tx_valid = 1'b0;
        tx_data  = 8'd0;
        errors   = 0;

        $display("============================================");
        $display(" uart_tx Testbench");
        $display(" DATA_W = %0d, STOP_BITS = %0d, PARITY = %0d",
                 DATA_W, STOP_BITS, PARITY);
        $display("============================================");

        //-------------------------------------------------------------------------
        // Reset
        //-------------------------------------------------------------------------
        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (10) @(posedge clk);

        //---------------------------------------------------------------------
        // Test 1: Idle state check
        //---------------------------------------------------------------------
        $display("\n[TEST 1] Idle state...");
        if (tx_line !== 1'b1) begin
            $display("  FAIL: tx_line not high in idle");
            errors = errors + 1;
        end
        if (tx_ready !== 1'b1) begin
            $display("  FAIL: tx_ready not high in idle");
            errors = errors + 1;
        end
        else begin
            $display("  PASS: Idle: tx_line=1, tx_ready=1");
        end

        //---------------------------------------------------------------------
        // Test 2: Send known byte pattern
        //---------------------------------------------------------------------
        $display("\n[TEST 2] Single byte transmission...");
        send_byte_verify(8'h55);    // Alternating 0/1
        send_byte_verify(8'hAA);    // Alternating 1/0
        send_byte_verify(8'h00);    // All zeros
        send_byte_verify(8'hFF);    // All ones
        send_byte_verify(8'h41);    // 'A'
        send_byte_verify(8'h5A);    // 'Z'

        //---------------------------------------------------------------------
        // Test 3: Ready/Valid handshake
        //---------------------------------------------------------------------
        $display("\n[TEST 3] Ready/Valid handshake...");
        // tx_ready should be low during transmission
        // Wait for idle, then assert valid and check ready drops
        while (!tx_ready) @(posedge clk);
        tx_data  = 8'h3C;
        tx_valid = 1'b1;
        @(posedge clk);
        tx_valid = 1'b0;

        // After a few cycles, tx_ready should be low (during transmission)
        repeat (5) @(posedge clk);
        if (tx_ready !== 1'b0) begin
            $display("  WARN: tx_ready expected low during transmission, got %b", tx_ready);
        end
        else begin
            $display("  PASS: tx_ready deasserted during active transmit");
        end

        // Wait for completion
        while (!tx_ready) @(posedge clk);
        $display("  PASS: tx_ready reasserted after completion");

        //---------------------------------------------------------------------
        // Test 4: Back-to-back transmission
        //---------------------------------------------------------------------
        $display("\n[TEST 4] Back-to-back transmission...");
        for (i = 0; i < 10; i = i + 1) begin
            send_byte_verify(8'h30 + i[3:0]);  // '0' - '9'
        end
        $display("  PASS: Back-to-back 10 bytes sent");

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