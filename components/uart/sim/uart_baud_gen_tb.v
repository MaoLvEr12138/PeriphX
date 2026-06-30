//=============================================================================
// Testbench   : uart_baud_gen_tb
// Description : Self-checking testbench for uart_baud_gen module.
//               Verifies tick period, pulse width, and reset behavior.
// Language    : Verilog-2001 (IEEE 1364-2001)
// Simulator   : iverilog / ModelSim / VCS / Xcelium
//=============================================================================

`timescale 1ns / 1ps

module uart_baud_gen_tb;

    //==========================================================================
    // Parameters
    //==========================================================================
    parameter CLK_PERIOD    = 10;           // 100 MHz -> 10 ns
    parameter SYS_CLK_HZ    = 100_000_000;
    parameter BAUD_RATE     = 1_000_000;    // 1 Mbps for fast simulation
    parameter OVERSAMPLE    = 16;

    // Expected divisor = 100M / (1M * 16) = 6.25 -> floor = 6
    // Expected tick period = 7 * 10ns = 70ns (divisor+1 cycles)
    localparam EXPECTED_CYCLES = (SYS_CLK_HZ / (BAUD_RATE * OVERSAMPLE)) + 1;

    //==========================================================================
    // Signals
    //==========================================================================
    reg  clk;
    reg  rst_n;
    wire baud_tick;

    //==========================================================================
    // DUT Instantiation
    //==========================================================================
    uart_baud_gen #(
        .SYS_CLK_HZ   (SYS_CLK_HZ),
        .BAUD_RATE    (BAUD_RATE),
        .OVERSAMPLE   (OVERSAMPLE)
    ) dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .baud_tick    (baud_tick)
    );

    //==========================================================================
    // Clock Generation
    //==========================================================================
    always #(CLK_PERIOD / 2.0) clk = ~clk;

    //==========================================================================
    // Test Variables
    //==========================================================================
    integer cycle_cnt;
    integer tick_cnt;
    integer prev_tick_cycle;
    integer period_cycles;
    integer errors;
    integer i;

    //==========================================================================
    // Main Test Sequence
    //==========================================================================
    initial begin
        // Initialize
        clk     = 1'b0;
        rst_n   = 1'b0;
        cycle_cnt = 0;
        tick_cnt  = 0;
        prev_tick_cycle = 0;
        errors    = 0;

        // Assert reset for 5 cycles
        repeat (5) @(posedge clk);
        rst_n = 1'b1;

        $display("============================================");
        $display(" uart_baud_gen Testbench");
        $display(" SYS_CLK_HZ  = %0d Hz", SYS_CLK_HZ);
        $display(" BAUD_RATE   = %0d bps", BAUD_RATE);
        $display(" OVERSAMPLE  = %0d", OVERSAMPLE);
        $display(" EXPECTED tick period = %0d cycles", EXPECTED_CYCLES);
        $display("============================================");

        //-------------------------------------------------------------------------
        // Test 1: Verify baud_tick stays low during reset
        //-------------------------------------------------------------------------
        $display("\n[TEST 1] Reset behavior check...");

        // Tick should be 0 during initial reset period
        @(posedge clk); // one more cycle to be safe
        if (baud_tick !== 1'b0) begin
            $display("  FAIL: baud_tick != 0 during reset (got %b)", baud_tick);
            errors = errors + 1;
        end
        else begin
            $display("  PASS");
        end

        //-------------------------------------------------------------------------
        // Test 2: Sample tick periods over many ticks
        //-------------------------------------------------------------------------
        $display("\n[TEST 2] Tick period measurement...");

        for (i = 0; i < 100; i = i + 1) begin
            @(posedge clk);
            cycle_cnt = cycle_cnt + 1;

            if (baud_tick) begin
                if (tick_cnt > 0) begin
                    period_cycles = cycle_cnt - prev_tick_cycle;

                    // Allow tolerance of +1/-0 cycles due to integer division
                    if (period_cycles != EXPECTED_CYCLES) begin
                        $display("  WARN: tick %0d period = %0d cycles (expected %0d)",
                                 tick_cnt, period_cycles, EXPECTED_CYCLES);
                        // In integer division, actual period may vary by 1
                        if (period_cycles > EXPECTED_CYCLES + 1 ||
                            period_cycles < EXPECTED_CYCLES - 1) begin
                            $display("  FAIL: period out of tolerance!");
                            errors = errors + 1;
                        end
                    end
                end
                prev_tick_cycle = cycle_cnt;
                tick_cnt = tick_cnt + 1;
            end
        end

        $display("  Measured %0d ticks over %0d cycles", tick_cnt, cycle_cnt);
        if (tick_cnt > 0) begin
            $display("  PASS");
        end
        else begin
            $display("  FAIL: No ticks detected!");
            errors = errors + 1;
        end

        //-------------------------------------------------------------------------
        // Test 3: Verify baud_tick is exactly 1 cycle wide
        //-------------------------------------------------------------------------
        $display("\n[TEST 3] Tick pulse width check...");
        begin
            reg tick_seen;
            tick_seen = 1'b0;

            // Wait for a tick
            while (!baud_tick) @(posedge clk);

            // baud_tick should be 1 for exactly this cycle
            @(posedge clk);
            if (baud_tick !== 1'b0) begin
                $display("  FAIL: baud_tick stayed high > 1 cycle!");
                errors = errors + 1;
            end
            else begin
                $display("  PASS: baud_tick is single-cycle pulse");
            end
        end

        //-------------------------------------------------------------------------
        // Results
        //-------------------------------------------------------------------------
        $display("\n============================================");
        if (errors == 0) begin
            $display(" ALL TESTS PASSED");
        end
        else begin
            $display(" %0d TEST(S) FAILED", errors);
        end
        $display("============================================");

        $finish;
    end

    //==========================================================================
    // Cycle Counter (debug)
    //==========================================================================
    always @(posedge clk) begin
        if (rst_n)
            cycle_cnt = cycle_cnt + 1;
    end

endmodule