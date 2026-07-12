`timescale 1ns/1ps


module tb_mlr_spi_slave();


////////////////////////////////////////////////////
// Clock
////////////////////////////////////////////////////

reg clk;

initial begin
    clk = 0;
end

always #10 clk = ~clk; 
// FPGA system clock 50MHz


////////////////////////////////////////////////////
// Reset
////////////////////////////////////////////////////

reg rst_n;


////////////////////////////////////////////////////
// SPI signals
////////////////////////////////////////////////////

reg spi_clk;
reg spi_cs_n;
reg spi_mosi;

wire spi_miso;



////////////////////////////////////////////////////
// DUT interface
////////////////////////////////////////////////////


wire rx_valid;
wire [7:0] rx_data;


reg tx_valid;
reg [7:0] tx_data;

wire tx_ready;


wire cs_start;
wire cs_end;
wire cs_active;



////////////////////////////////////////////////////
// DUT
////////////////////////////////////////////////////


mlr_spi_slave dut
(
    .clk(clk),
    .rst_n(rst_n),

    .spi_clk(spi_clk),
    .spi_cs_n(spi_cs_n),
    .spi_mosi(spi_mosi),
    .spi_miso(spi_miso),

    .rx_valid(rx_valid),
    .rx_data(rx_data),

    .tx_valid(tx_valid),
    .tx_data(tx_data),
    .tx_ready(tx_ready),

    .cs_start(cs_start),
    .cs_end(cs_end),
    .cs_active(cs_active)
);



////////////////////////////////////////////////////
// SPI master task
////////////////////////////////////////////////////


// Mode 0
//
// idle clk = 0
//
// MOSI setup before rising edge
// sample on rising edge
//

task spi_write_byte;

input [7:0] data;

integer i;


begin

    for(i=7;i>=0;i=i-1)
    begin

        spi_mosi = data[i];


        #50;

        spi_clk = 1;


        #50;

        spi_clk = 0;


    end

end

endtask



////////////////////////////////////////////////////
// Test sequence
////////////////////////////////////////////////////


initial begin


    $dumpfile("spi_test.vcd");
    $dumpvars(0,tb_mlr_spi_slave);



    //
    // initial
    //

    spi_clk = 0;
    spi_cs_n = 1;
    spi_mosi = 0;

    tx_valid = 0;
    tx_data = 0;


    rst_n = 0;


    #200;


    rst_n = 1;


    #200;



    ////////////////////////////////////////////////////
    //
    // Test 1:
    // single byte
    //
    ////////////////////////////////////////////////////


    $display("TEST 1");


    spi_cs_n = 0;


    spi_write_byte(8'hA5);


    spi_cs_n = 1;



    #500;



    ////////////////////////////////////////////////////
    //
    // Test 2:
    // MLR frame
    //
    ////////////////////////////////////////////////////


    $display("TEST 2");


    spi_cs_n = 0;


    spi_write_byte(8'h55);

    spi_write_byte(8'h00);

    spi_write_byte(8'h01);

    spi_write_byte(8'h00);

    spi_write_byte(8'h12);

    spi_write_byte(8'h34);

    spi_write_byte(8'h56);

    spi_write_byte(8'h78);


    spi_cs_n = 1;


    #1000;



    ////////////////////////////////////////////////////
    //
    // finish
    //
    ////////////////////////////////////////////////////


    $display("DONE");

    #1000;


    $finish;


end



////////////////////////////////////////////////////
// monitor RX
////////////////////////////////////////////////////


always @(posedge clk)
begin

    if(rx_valid)
    begin

        $display(
            "RX BYTE = %02X  time=%0t",
            rx_data,
            $time
        );

    end


end



endmodule