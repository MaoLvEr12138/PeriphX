module spi_slave
(
    input  wire clk,
    input  wire rst_n,


    // SPI interface
    input  wire spi_clk,
    input  wire spi_cs_n,
    input  wire spi_mosi,
    output wire spi_miso,


    // RX byte interface
    output reg        rx_valid,
    output reg [7:0]  rx_data,


    // TX byte interface
    input  wire       tx_valid,
    input  wire [7:0] tx_data,
    output reg        tx_ready,


    // CS events
    output reg cs_active,
    output reg cs_start,
    output reg cs_end
);



////////////////////////////////////////////////////
//
// SPI clock domain
//
////////////////////////////////////////////////////


reg [7:0] rx_shift;
reg [7:0] tx_shift;


reg [2:0] rx_bit_cnt;
reg [2:0] tx_bit_cnt;


reg rx_toggle;



//
// RX
//
// Mode 0:
// sample MOSI rising edge
//

always @(posedge spi_clk or posedge spi_cs_n)
begin

    if(spi_cs_n)
    begin

        rx_bit_cnt <= 0;

    end

    else
    begin

        rx_shift <= {
            rx_shift[6:0],
            spi_mosi
        };


        if(rx_bit_cnt == 3'd7)
        begin

            rx_bit_cnt <= 0;

            rx_toggle <= ~rx_toggle;

        end

        else
        begin

            rx_bit_cnt <= rx_bit_cnt + 1'b1;

        end

    end

end



//
// TX
//
// change MOSI on falling edge
//

always @(negedge spi_clk or posedge spi_cs_n)
begin

    if(spi_cs_n)
    begin

        tx_bit_cnt <= 3'd7;

        tx_shift <= 8'h00;

    end

    else
    begin

        if(tx_bit_cnt != 0)
        begin

            tx_bit_cnt <= tx_bit_cnt - 1'b1;

        end

    end

end



assign spi_miso =
        spi_cs_n ?
        1'bz :
        tx_shift[tx_bit_cnt];



//
// Load next TX byte
//

always @(posedge spi_clk or posedge spi_cs_n)
begin

    if(spi_cs_n)
    begin

        tx_shift <= 8'h00;

    end

    else
    begin

        if(tx_bit_cnt == 0)
        begin

            if(tx_valid)
                tx_shift <= tx_data;

        end

    end

end



////////////////////////////////////////////////////
//
// Clock domain crossing
//
////////////////////////////////////////////////////


reg rx_sync1;
reg rx_sync2;


always @(posedge clk or negedge rst_n)
begin

    if(!rst_n)
    begin

        rx_sync1 <= 0;
        rx_sync2 <= 0;

        rx_valid <= 0;

        rx_data <= 0;

    end

    else
    begin

        rx_sync1 <= rx_toggle;
        rx_sync2 <= rx_sync1;


        rx_valid <= 0;


        if(rx_sync1 != rx_sync2)
        begin

            rx_valid <= 1;

            rx_data <= rx_shift;

        end

    end

end



////////////////////////////////////////////////////
//
// TX request
//
////////////////////////////////////////////////////


always @(posedge clk or negedge rst_n)
begin

    if(!rst_n)
    begin

        tx_ready <= 0;

    end

    else
    begin

        tx_ready <= 0;


        if(!spi_cs_n)
        begin

            if(tx_bit_cnt == 0)
                tx_ready <= 1;

        end

    end

end



////////////////////////////////////////////////////
//
// CS detect
//
////////////////////////////////////////////////////


reg cs_last;


always @(posedge clk or negedge rst_n)
begin

    if(!rst_n)
    begin

        cs_last <= 1;

        cs_active <= 0;

        cs_start <= 0;

        cs_end <= 0;

    end

    else
    begin

        cs_last <= spi_cs_n;


        cs_active <= !spi_cs_n;


        cs_start <= 0;

        cs_end <= 0;


        if(cs_last && !spi_cs_n)
            cs_start <= 1;


        if(!cs_last && spi_cs_n)
            cs_end <= 1;


    end

end


endmodule