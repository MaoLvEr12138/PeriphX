/* verilator lint_off UNUSED */
/* verilator lint_off SYNCASYNCNET */

// Byte-oriented SPI Mode 0 slave.
// Drive spi_* from the external SPI master.
// Use rx_valid/rx_data to read received bytes in clk domain.
// Present tx_valid/tx_data in clk domain before the next frame.
module spi_slave
(
    input  wire clk,
    input  wire rst_n,

    // SPI mode0
    input  wire spi_clk,
    input  wire spi_cs_n,
    input  wire spi_mosi,
    output wire spi_miso,

    // RX
    output reg        rx_valid,
    output reg [7:0]  rx_data,

    // TX
    input  wire       tx_valid,
    input  wire [7:0] tx_data,
    output reg        tx_ready,

    // CS
    output reg cs_active,
    output reg cs_start,
    output reg cs_end
);

//////////////////////////////////////////////////////
// SPI clock domain
//////////////////////////////////////////////////////

reg [7:0] rx_shift_spi;
reg [2:0] rx_count_spi;
reg [7:0] rx_byte_spi;
reg rx_toggle_spi;

reg [7:0] tx_shift_spi;
reg [7:0] tx_stage_spi;
reg [7:0] tx_load_spi;
reg [2:0] tx_count_spi;
// Marks the first byte after CS goes low.
reg tx_first_spi;
reg tx_req_toggle;

//////////////////////////////////////////////////////
// CDC state
//////////////////////////////////////////////////////

reg rx_toggle_sync1;
reg rx_toggle_sync2;
reg rx_toggle_last;
reg rx_event_pending;
reg [7:0] rx_byte_sync1;
reg [7:0] rx_byte_sync2;

reg tx_req_sync1;
reg tx_req_sync2;
reg tx_req_last;

//////////////////////////////////////////////////////
// RX
//
// Mode0: sample on rising edge
//////////////////////////////////////////////////////

always @(posedge spi_clk or posedge spi_cs_n or negedge rst_n)
begin
    if(!rst_n)
    begin
        rx_shift_spi <= 8'h00;
        rx_count_spi <= 3'd0;
        rx_byte_spi  <= 8'h00;
        rx_toggle_spi <= 1'b0;
    end
    else if(spi_cs_n)
    begin
        rx_shift_spi <= 8'h00;
        rx_count_spi <= 3'd0;
    end
    else
    begin
        rx_shift_spi <= {
            rx_shift_spi[6:0],
            spi_mosi
        };

        if(rx_count_spi == 3'd7)
        begin
            rx_count_spi <= 3'd0;
            rx_byte_spi  <= {
                rx_shift_spi[6:0],
                spi_mosi
            };
            rx_toggle_spi <= ~rx_toggle_spi;
        end
        else
        begin
            rx_count_spi <= rx_count_spi + 3'd1;
        end
    end
end

//////////////////////////////////////////////////////
// TX shift
//////////////////////////////////////////////////////

// Keep the TX byte preloaded in the SPI domain and expose the staged byte
// directly for the first byte so Mode 0 sees a stable MSB on the very first
// rising SCK edge after CS goes low.
always @(negedge spi_clk or posedge spi_cs_n or negedge rst_n)
begin
    if(!rst_n)
    begin
        tx_count_spi <= 3'd7;
        tx_shift_spi  <= 8'h00;
        tx_stage_spi  <= 8'h00;
        tx_first_spi  <= 1'b1;
    end
    else if(spi_cs_n)
    begin
        tx_count_spi <= 3'd7;
        tx_shift_spi  <= tx_load_spi;
        tx_stage_spi  <= tx_load_spi;
        tx_first_spi  <= 1'b1;
    end
    else if(tx_first_spi)
    begin
        // The first falling edge after CS low consumes bit7 and advances the
        // shifter to bit6 so the next rising edge sees a clean byte cadence.
        tx_count_spi <= 3'd6;
        tx_shift_spi  <= {
            tx_shift_spi[6:0],
            1'b0
        };
        tx_stage_spi  <= tx_load_spi;
        tx_first_spi  <= 1'b0;
    end
    else
    begin
        tx_stage_spi <= tx_load_spi;

        if(tx_count_spi == 0)
        begin
            tx_count_spi <= 3'd7;
            // Load the pre-sampled byte from the SPI-domain stage register.
            tx_shift_spi <= tx_stage_spi;
            tx_first_spi <= 1'b0;
        end
        else
        begin
            tx_count_spi <= tx_count_spi - 3'd1;
            tx_shift_spi <= {
                tx_shift_spi[6:0],
                1'b0
            };
            tx_first_spi <= 1'b0;
        end
    end
end

//////////////////////////////////////////////////////
// MISO
//////////////////////////////////////////////////////

assign spi_miso =
        spi_cs_n ?
        1'bz :
        (tx_first_spi ? tx_stage_spi[7] : tx_shift_spi[7]);

//////////////////////////////////////////////////////
// TX byte loading
//
// Keep the byte stable in the clk domain so the SPI domain can sample it.
//////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        tx_load_spi <= 8'h00;
    end
    else if(tx_valid)
    begin
        tx_load_spi <= tx_data;
    end
end

//////////////////////////////////////////////////////
// CDC RX
//////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        rx_toggle_sync1 <= 1'b0;
        rx_toggle_sync2 <= 1'b0;
        rx_toggle_last  <= 1'b0;
        rx_event_pending <= 1'b0;
        rx_byte_sync1   <= 8'h00;
        rx_byte_sync2   <= 8'h00;
        rx_valid        <= 1'b0;
        rx_data         <= 8'h00;
    end
    else
    begin
        rx_toggle_sync1 <= rx_toggle_spi;
        rx_toggle_sync2 <= rx_toggle_sync1;
        rx_byte_sync1   <= rx_byte_spi;
        rx_byte_sync2   <= rx_byte_sync1;

        rx_valid <= 1'b0;

        if(rx_event_pending)
        begin
            rx_data         <= rx_byte_sync2;
            rx_valid        <= 1'b1;
            rx_event_pending <= 1'b0;
        end

        if(rx_toggle_sync2 != rx_toggle_last)
        begin
            rx_toggle_last   <= rx_toggle_sync2;
            rx_event_pending  <= 1'b1;
        end
    end
end

//////////////////////////////////////////////////////
// CDC TX
//////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        tx_req_sync1 <= 1'b0;
        tx_req_sync2 <= 1'b0;
        tx_req_last  <= 1'b0;
        tx_ready     <= 1'b0;
    end
    else
    begin
        tx_req_sync1 <= tx_req_toggle;
        tx_req_sync2 <= tx_req_sync1;

        tx_ready <= 1'b0;

        if(tx_req_sync2 != tx_req_last)
        begin
            tx_req_last <= tx_req_sync2;
            tx_ready    <= 1'b1;
        end
    end
end

//////////////////////////////////////////////////////
// TX request generation
//////////////////////////////////////////////////////

always @(posedge spi_clk or posedge spi_cs_n or negedge rst_n)
begin
    if(!rst_n)
    begin
        tx_req_toggle <= 1'b0;
    end
    else if(spi_cs_n)
    begin
        tx_req_toggle <= 1'b0;
    end
    else if(tx_count_spi == 3'd7)
    begin
        // Raise a byte-ready pulse right at the start of a byte so the next
        // byte gets a full-byte window to settle before the boundary.
        tx_req_toggle <= ~tx_req_toggle;
    end
end

//////////////////////////////////////////////////////
// CS detect
//////////////////////////////////////////////////////

reg cs_last;

always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        cs_last   <= 1'b1;
        cs_active <= 1'b0;
        cs_start  <= 1'b0;
        cs_end    <= 1'b0;
    end
    else
    begin
        cs_last   <= spi_cs_n;
        cs_active <= !spi_cs_n;
        cs_start  <= 1'b0;
        cs_end    <= 1'b0;

        if(cs_last && !spi_cs_n)
            cs_start <= 1'b1;

        if(!cs_last && spi_cs_n)
            cs_end <= 1'b1;
    end
end

/* verilator lint_on SYNCASYNCNET */
/* verilator lint_on UNUSED */

endmodule
