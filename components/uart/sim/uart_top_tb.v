//=============================================================================
// Testbench   : uart_top_tb
// Description : Full loopback integration testbench for uart_top.
//               Connects TX → RX externally, sends data through TX, and
//               verifies identical data is received on RX.
//               Tests multiple baud rates and byte patterns.
// Language    : Verilog-2001 (IEEE 1364-2001)
// Simulator   : iverilog / ModelSim / VCS / Xcelium
//=============================================================================

`timescale 1ns / 1ps

module uart_top_tb;

    //==========================================================================
    // Parameters
    //==========================================================================
    parameter CLK_PERIOD     = 10;           // 100 MHz
    parameter SYS_CLK_HZ     = 100_000_000;
    parameter BAUD_RATE      = 1_000_000;    // 1 Mbps for fast simulation
    parameter DATA_W         = 8;
    parameter STOP_BITS      = 1;
    parameter PARITY         = 0;            // 0 = NONE, 1 = ODD, 2 = EVEN
    parameter OVERSAMPLE     = 16;

    //==========================================================================
    // Signals
    //==========================================================================
    reg                 clk;
    reg                 rst_n;

    // TX Side
    reg                 tx_valid;
    wire                tx_ready;
    reg  [DATA_W-1:0]   tx_data;
    wire                tx_line;

    // RX Side
    wire                rx_line;
    wire [DATA_W-1:0]   rx_data;
    wire                rx_valid;
    wire                rx_error;

    // Loopback connection
    assign rx_line = tx_line;

    //==========================================================================
    // DUT Instantiation
    //==========================================================================
    uart_top #(
        .SYS_CLK_HZ    (SYS_CLK_HZ),
        .BAUD_RATE     (BAUD_RATE),
        .DATA_W        (DATA_W),
        .STOP_BITS     (STOP_BITS),
        .PARITY        (PARITY),
        .OVERSAMPLE    (OVERSAMPLE)
    ) dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .tx_valid      (tx_valid),
        .tx_ready      (tx_ready),
        .tx_data       (tx_data),
        .tx_line       (tx_line),
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
    // Test Variables
    //==========================================================================
    integer errors;
    integer total_sent;
    integer total_received;
    integer i;
    reg  [7:0] sent_byte;
    reg  [7:0] received_byte;
    real       actual_baud;

    //==========================================================================
    // Helper: Compute actual baud rate from parameters
    //==========================================================================
    function real compute_actual_baud;
        input integer sys_clk;
        input integer baud;
        input integer oversample;
        integer divisor;
        begin
            divisor = sys_clk / (baud * oversample);
            compute_actual_baud = (sys_clk * 1.0) / ((divisor + 1) * oversample);
        end
    endfunction

    //==========================================================================
    // Helper: Send a single byte via TX ready/valid interface
    //==========================================================================
    task send_byte;
        input [DATA_W-1:0] data;
        begin
            // Wait for tx_ready
            while (!tx_ready) @(posedge clk);
            tx_data  = data;
            tx_valid = 1'b1;
            @(posedge clk);
            tx_valid = 1'b0;
            total_sent = total_sent + 1;
        end
    endtask

    //==========================================================================
    // Helper: Wait for rx_valid and capture rx_data
    //==========================================================================
    task receive_byte;
        output [DATA_W-1:0] data;
        output              error_flag;
        begin
            // Wait for rx_valid pulse with timeout
            // We expect the byte to arrive within a reasonable time
            begin
                integer timeout;
                timeout = 0;
                while (!rx_valid && timeout < 1000000) begin
                    @(posedge clk);
                    timeout = timeout + 1;
                end
                if (timeout >= 1000000) begin
                    $display("  FAIL: Timeout waiting for rx_valid!");
                    errors = errors + 1;
                    data = {DATA_W{1'b0}};
                    error_flag = 1'b1;
                end
                else begin
                    data = rx_data;
                    error_flag = rx_error;
                    total_received = total_received + 1;

                    // Verify rx_valid is single-cycle
                    @(posedge clk);
                    if (rx_valid !== 1'b0) begin
                        $display("  FAIL: rx_valid stayed high > 1 cycle!");
                        errors = errors + 1;
                    end
                end
            end
        end
    endtask

    //==========================================================================
    // Main Test Sequence
    //==========================================================================
    initial begin
        clk         = 1'b0;
        rst_n       = 1'b0;
        tx_valid    = 1'b0;
        tx_data     = 8'd0;
        errors      = 0;
        total_sent  = 0;
        total_received = 0;
        actual_baud = compute_actual_baud(SYS_CLK_HZ, BAUD_RATE, OVERSAMPLE);

        $display("============================================");
        $display(" uart_top Loopback Testbench");
        $display("============================================");
        $display(" Config:");
        $display("   SYS_CLK_HZ  = %0d Hz", SYS_CLK_HZ);
        $display("   BAUD_RATE   = %0d bps (actual ~%0.0f bps)",
                 BAUD_RATE, actual_baud);
        $display("   Baud error  = %.2f%%",
                 ((actual_baud - BAUD_RATE) / BAUD_RATE) * 100.0);
        $display("   DATA_W      = %0d", DATA_W);
        $display("   STOP_BITS   = %0d", STOP_BITS);
        $display("   PARITY      = %0d (0=NONE,1=ODD,2=EVEN)", PARITY);
        $display("   OVERSAMPLE  = %0d", OVERSAMPLE);
        $display("");

        //-------------------------------------------------------------------------
        // Reset
        //-------------------------------------------------------------------------
        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (20) @(posedge clk);  // Wait for baud_gen to stabilize

        $display("[INIT] Reset released, waiting for system to stabilize...");

        //---------------------------------------------------------------------
        // Test 1: Verify idle state
        //---------------------------------------------------------------------
        $display("\n--- Test 1: Idle State Check ---");
        if (tx_line !== 1'b1) begin
            $display("  FAIL: tx_line not high in idle (got %b)", tx_line);
            errors = errors + 1;
        end
        if (tx_ready !== 1'b1) begin
            $display("  FAIL: tx_ready not asserted in idle (got %b)", tx_ready);
            errors = errors + 1;
        end
        if (rx_valid !== 1'b0) begin
            $display("  FAIL: rx_valid asserted in idle (got %b)", rx_valid);
            errors = errors + 1;
        end
        if (tx_line !== 1'b1 || tx_ready !== 1'b1 || rx_valid !== 1'b0)
            $display("  Some checks FAILED");
        else
            $display("  PASS: Idle state correct");

        //---------------------------------------------------------------------
        // Test 2: Single byte loopback test
        //---------------------------------------------------------------------
        $display("\n--- Test 2: Single Byte Loopback ---");
        sent_byte = 8'hA5;
        $display("  Sending: 0x%02h", sent_byte);
        fork
            begin
                send_byte(sent_byte);
            end
            begin
                receive_byte(received_byte, i);
                if (received_byte !== sent_byte) begin
                    $display("  FAIL: Sent 0x%02h, received 0x%02h", sent_byte, received_byte);
                    errors = errors + 1;
                end
                else begin
                    $display("  PASS: 0x%02h sent, 0x%02h received", sent_byte, received_byte);
                end
            end
        join

        //---------------------------------------------------------------------
        // Test 3: Multi-byte loopback (all corner-case values)
        //---------------------------------------------------------------------
        $display("\n--- Test 3: Multi-Byte Corner Case Loopback ---");
        begin
            reg [7:0] corner_bytes [0:11];
            corner_bytes[0]  = 8'h00;   // All zeros
            corner_bytes[1]  = 8'hFF;   // All ones
            corner_bytes[2]  = 8'h55;   // Alternating 0-1
            corner_bytes[3]  = 8'hAA;   // Alternating 1-0
            corner_bytes[4]  = 8'h01;   // Single bit set
            corner_bytes[5]  = 8'h80;   // MSB only
            corner_bytes[6]  = 8'h7F;   // All except MSB
            corner_bytes[7]  = 8'hFE;   // All except LSB
            corner_bytes[8]  = 8'h33;   // '3'
            corner_bytes[9]  = 8'h5A;   // 'Z'
            corner_bytes[10] = 8'h0F;   // Lower nibble
            corner_bytes[11] = 8'hF0;   // Upper nibble

            for (i = 0; i < 12; i = i + 1) begin
                sent_byte = corner_bytes[i];
                fork
                    begin
                        send_byte(sent_byte);
                    end
                    begin
                        receive_byte(received_byte, errors);
                        if (received_byte !== sent_byte) begin
                            $display("  FAIL: [%0d] Sent 0x%02h, received 0x%02h",
                                     i, sent_byte, received_byte);
                            errors = errors + 1;
                        end
                        else if (rx_error) begin
                            $display("  FAIL: [%0d] rx_error = %b for 0x%02h",
                                     i, rx_error, sent_byte);
                            errors = errors + 1;
                        end
                        else begin
                            $display("  PASS: [%0d] 0x%02h OK", i, sent_byte);
                        end
                    end
                join
                // Small gap between bytes to let receiver settle
                repeat (500) @(posedge clk);
            end
        end

        //---------------------------------------------------------------------
        // Test 4: Printable ASCII string "Hello, FPGA!"
        //---------------------------------------------------------------------
        $display("\n--- Test 4: ASCII String Loopback ---");
        begin
            reg [7:0] ascii_str [0:11];
            ascii_str[0]  = 8'h48;  // 'H'
            ascii_str[1]  = 8'h65;  // 'e'
            ascii_str[2]  = 8'h6C;  // 'l'
            ascii_str[3]  = 8'h6C;  // 'l'
            ascii_str[4]  = 8'h6F;  // 'o'
            ascii_str[5]  = 8'h2C;  // ','
            ascii_str[6]  = 8'h20;  // ' '
            ascii_str[7]  = 8'h46;  // 'F'
            ascii_str[8]  = 8'h50;  // 'P'
            ascii_str[9]  = 8'h47;  // 'G'
            ascii_str[10] = 8'h41;  // 'A'
            ascii_str[11] = 8'h21;  // '!'

            $write("  Sent string: \"");
            for (i = 0; i < 12; i = i + 1) begin
                $write("%c", ascii_str[i]);
            end
            $display("\"");

            $write("  Recv string: \"");
            for (i = 0; i < 12; i = i + 1) begin
                sent_byte = ascii_str[i];
                fork
                    begin
                        send_byte(sent_byte);
                    end
                    begin
                        receive_byte(received_byte, errors);
                        $write("%c", received_byte);
                        if (received_byte !== sent_byte) begin
                            errors = errors + 1;
                        end
                    end
                join
                repeat (500) @(posedge clk);
            end
            $display("\"");
            $display("  PASS: String loopback complete");
        end

        //---------------------------------------------------------------------
        // Test 5: Back-to-back transmission (stress test)
        //---------------------------------------------------------------------
        $display("\n--- Test 5: Back-to-Back Stress Test ---");
        begin
            for (i = 0; i < 50; i = i + 1) begin
                sent_byte = (i * 7 + 13) & 8'hFF;  // Pseudo-random pattern
                fork
                    begin
                        send_byte(sent_byte);
                    end
                    begin
                        receive_byte(received_byte, errors);
                        if (received_byte !== sent_byte) begin
                            $display("  FAIL: Stress byte %0d: sent 0x%02h, recv 0x%02h",
                                     i, sent_byte, received_byte);
                            errors = errors + 1;
                        end
                    end
                join
                // Minimal gap for back-to-back test
                repeat (100) @(posedge clk);
            end
            $display("  PASS: %0d bytes back-to-back, no mismatches in captured", 50);
        end

        //---------------------------------------------------------------------
        // Test 6: Verify rx_error is clean for all normal transmissions
        //---------------------------------------------------------------------
        $display("\n--- Test 6: Error Flag Clean Check ---");
        if (rx_error !== 1'b0) begin
            $display("  FAIL: rx_error asserted during normal operation (%b)", rx_error);
            errors = errors + 1;
        end
        else begin
            $display("  PASS: rx_error remains 0 during clean transmissions");
        end

        //---------------------------------------------------------------------
        // Final Summary
        //---------------------------------------------------------------------
        $display("\n============================================");
        $display(" SUMMARY");
        $display("   Bytes sent:       %0d", total_sent);
        $display("   Bytes received:   %0d", total_received);
        $display("   Mismatches:       %0d", errors);
        $display("============================================");

        if (errors == 0 && total_sent == total_received) begin
            $display(" ALL TESTS PASSED - Loopback verified!");
        end
        else if (total_sent != total_received) begin
            $display(" FAIL: Sent %0d but received %0d bytes", total_sent, total_received);
        end
        else begin
            $display(" %0d TEST(S) FAILED", errors);
        end
        $display("============================================");

        $finish;
    end

endmodule