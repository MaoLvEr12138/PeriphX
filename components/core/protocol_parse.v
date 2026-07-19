// Byte-level frame bridge.
// RX: spi_slave bytes -> frame output.
// TX: frame input -> spi_slave bytes.
module protocol_parse
(
    input  wire clk,
    input  wire rst_n,

    // SPI pins
    input  wire spi_clk,
    input  wire spi_cs_n,
    input  wire spi_mosi,
    output wire spi_miso,

    // SPI side frame markers
    output wire cs_active,
    output wire cs_start,
    output wire cs_end,

    // Frame TX from business logic to MCU
    input  wire       tx_frame_valid,
    output wire       tx_frame_ready,
    input  wire [7:0] tx_server_id,
    input  wire [31:0] tx_payload,
    input  wire [3:0] tx_msg_type,

    // Frame RX from MCU to business logic
    output reg        rx_frame_valid,
    output reg        rx_frame_error,
    output reg [7:0]  rx_server_id,
    output reg [31:0] rx_payload,
    output reg [3:0]  rx_msg_type,
    output reg [3:0]  rx_crc4
);

localparam [2:0] FRAME_LAST = 3'd5;
localparam [7:0] TURNAROUND_BYTE = 8'hFF;

//////////////////////////////////////////////////////
// Frame layout
//
// byte0: server_id
// byte1: payload[31:24]
// byte2: payload[23:16]
// byte3: payload[15:8]
// byte4: payload[7:0]
// byte5: {crc4[7:4], msg_type[3:0]}
//
// CRC4 uses poly x^4 + x + 1, MSB first, seed = 0.
//////////////////////////////////////////////////////

// Advance one CRC bit.
function [3:0] crc4_step;
    input [3:0] crc_in;
    input       bit_in;
    reg         fb;
    reg [3:0]   crc_out;
    begin
        fb = crc_in[3] ^ bit_in;
        crc_out = {crc_in[2:0], 1'b0};
        if(fb)
            crc_out = crc_out ^ 4'h3;
        crc4_step = crc_out;
    end
endfunction

// Fold one byte into the running CRC.
function [3:0] crc4_byte;
    input [3:0] crc_in;
    input [7:0] data;
    integer i;
    reg [3:0] crc_tmp;
    begin
        crc_tmp = crc_in;
        for(i = 7; i >= 0; i = i - 1)
            crc_tmp = crc4_step(crc_tmp, data[i]);
        crc4_byte = crc_tmp;
    end
endfunction

// Fold one nibble into the running CRC.
function [3:0] crc4_nibble;
    input [3:0] crc_in;
    input [3:0] data;
    integer i;
    reg [3:0] crc_tmp;
    begin
        crc_tmp = crc_in;
        for(i = 3; i >= 0; i = i - 1)
            crc_tmp = crc4_step(crc_tmp, data[i]);
        crc4_nibble = crc_tmp;
    end
endfunction

// Build the CRC over the fixed frame fields.
function [3:0] crc4_frame;
    input [7:0]  server_id;
    input [31:0] payload;
    input [3:0]  msg_type;
    reg [3:0] crc_tmp;
    begin
        crc_tmp = 4'h0;
        crc_tmp = crc4_byte(crc_tmp, server_id);
        crc_tmp = crc4_byte(crc_tmp, payload[31:24]);
        crc_tmp = crc4_byte(crc_tmp, payload[23:16]);
        crc_tmp = crc4_byte(crc_tmp, payload[15:8]);
        crc_tmp = crc4_byte(crc_tmp, payload[7:0]);
        crc_tmp = crc4_nibble(crc_tmp, msg_type);
        crc4_frame = crc_tmp;
    end
endfunction

//////////////////////////////////////////////////////
// SPI byte transport
//////////////////////////////////////////////////////

wire       spi_rx_valid;
wire [7:0] spi_rx_data;
wire       spi_tx_ready;
reg        spi_tx_valid;
reg [7:0]  spi_tx_data;

spi_slave u_spi_slave
(
    .clk       (clk),
    .rst_n     (rst_n),

    .spi_clk   (spi_clk),
    .spi_cs_n  (spi_cs_n),
    .spi_mosi  (spi_mosi),
    .spi_miso  (spi_miso),

    .rx_valid  (spi_rx_valid),
    .rx_data   (spi_rx_data),

    .tx_valid  (spi_tx_valid),
    .tx_data   (spi_tx_data),
    .tx_ready  (spi_tx_ready),

    .cs_active (cs_active),
    .cs_start  (cs_start),
    .cs_end    (cs_end)
);

//////////////////////////////////////////////////////
// RX frame assembly
//////////////////////////////////////////////////////

reg [2:0] rx_index;
reg       rx_done;
reg [3:0] rx_crc_acc;

reg [7:0] rx_b0;
reg [7:0] rx_b1;
reg [7:0] rx_b2;
reg [7:0] rx_b3;
reg [7:0] rx_b4;
always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        rx_index       <= 3'd0;
        rx_done        <= 1'b0;
        rx_crc_acc     <= 4'h0;
        rx_b0          <= 8'h00;
        rx_b1          <= 8'h00;
        rx_b2          <= 8'h00;
        rx_b3          <= 8'h00;
        rx_b4          <= 8'h00;
        rx_frame_valid <= 1'b0;
        rx_frame_error <= 1'b0;
        rx_server_id   <= 8'h00;
        rx_payload     <= 32'h0000_0000;
        rx_msg_type    <= 4'h0;
        rx_crc4        <= 4'h0;
    end
    else
    begin
        rx_frame_valid <= 1'b0;
        rx_frame_error <= 1'b0;

        if(cs_start)
        begin
            // Start a new fixed-size frame.
            rx_index   <= 3'd0;
            rx_done    <= 1'b0;
            rx_crc_acc <= 4'h0;
        end

        if(spi_rx_valid)
        begin
            if(!rx_done)
            begin
                case(rx_index)
                    3'd0:
                    begin
                        rx_b0      <= spi_rx_data;
                        rx_crc_acc <= crc4_byte(4'h0, spi_rx_data);
                        rx_index   <= 3'd1;
                    end

                    3'd1:
                    begin
                        rx_b1      <= spi_rx_data;
                        rx_crc_acc <= crc4_byte(rx_crc_acc, spi_rx_data);
                        rx_index   <= 3'd2;
                    end

                    3'd2:
                    begin
                        rx_b2      <= spi_rx_data;
                        rx_crc_acc <= crc4_byte(rx_crc_acc, spi_rx_data);
                        rx_index   <= 3'd3;
                    end

                    3'd3:
                    begin
                        rx_b3      <= spi_rx_data;
                        rx_crc_acc <= crc4_byte(rx_crc_acc, spi_rx_data);
                        rx_index   <= 3'd4;
                    end

                    3'd4:
                    begin
                        rx_b4      <= spi_rx_data;
                        rx_crc_acc <= crc4_byte(rx_crc_acc, spi_rx_data);
                        rx_index   <= 3'd5;
                    end

                    FRAME_LAST:
                    begin
                        rx_server_id <= rx_b0;
                        rx_payload   <= {rx_b1, rx_b2, rx_b3, rx_b4};
                        rx_msg_type  <= spi_rx_data[3:0];
                        rx_crc4      <= spi_rx_data[7:4];

                        if(crc4_nibble(rx_crc_acc, spi_rx_data[3:0]) == spi_rx_data[7:4])
                            rx_frame_valid <= 1'b1;
                        else
                            rx_frame_error <= 1'b1;

                        rx_done  <= 1'b1;
                        rx_index <= 3'd0;
                    end

                    default:
                    begin
                        rx_frame_error <= 1'b1;
                        rx_done        <= 1'b1;
                        rx_index       <= 3'd0;
                    end
                endcase
            end
            else
            begin
                rx_frame_error <= 1'b1;
            end
        end
    end
end

//////////////////////////////////////////////////////
// TX frame serialization
//////////////////////////////////////////////////////

reg        tx_busy;
// 0..2 = turnaround, 3..8 = response bytes.
reg [3:0]  tx_index;
reg [7:0]  tx_b1;
reg [7:0]  tx_b2;
reg [7:0]  tx_b3;
reg [7:0]  tx_b4;
reg [7:0]  tx_b5;

assign tx_frame_ready = !tx_busy;

always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        tx_busy        <= 1'b0;
        tx_index       <= 3'd0;
        tx_b1          <= 8'h00;
        tx_b2          <= 8'h00;
        tx_b3          <= 8'h00;
        tx_b4          <= 8'h00;
        tx_b5          <= 8'h00;
        spi_tx_valid   <= 1'b0;
        spi_tx_data    <= 8'h00;
    end
    else
    begin
        if(cs_end)
        begin
            // Drop any pending TX frame when CS ends.
            spi_tx_valid <= 1'b0;
            tx_busy      <= 1'b0;
            tx_index     <= 3'd0;
        end
        else if(!tx_busy)
        begin
            spi_tx_valid <= 1'b0;

            if(tx_frame_valid)
            begin
                // Latch the frame and precompute the CRC nibble.
                //
                // The first SPI byte after the request is an intentional
                // turnaround byte. This keeps the response aligned to a
                // clean byte boundary after the request frame has fully
                // drained through the parser/router path.
                tx_b1 <= tx_payload[31:24];
                tx_b2 <= tx_payload[23:16];
                tx_b3 <= tx_payload[15:8];
                tx_b4 <= tx_payload[7:0];
                tx_b5 <= {crc4_frame(tx_server_id, tx_payload, tx_msg_type), tx_msg_type};

                tx_busy      <= 1'b1;
                tx_index     <= 4'd0;
                spi_tx_valid <= 1'b1;
                spi_tx_data  <= TURNAROUND_BYTE;
            end
        end
        else
        begin
            spi_tx_valid <= 1'b1;

            if(spi_tx_ready)
            begin
                case(tx_index)
                    4'd0:
                    begin
                        tx_index    <= 4'd1;
                        spi_tx_data <= TURNAROUND_BYTE;
                    end

                    4'd1:
                    begin
                        tx_index    <= 4'd2;
                        spi_tx_data <= TURNAROUND_BYTE;
                    end

                    4'd2:
                    begin
                        tx_index    <= 4'd3;
                        spi_tx_data <= tx_server_id;
                    end

                    4'd3:
                    begin
                        tx_index    <= 4'd4;
                        spi_tx_data <= tx_b1;
                    end

                    4'd4:
                    begin
                        tx_index    <= 4'd5;
                        spi_tx_data <= tx_b2;
                    end

                    4'd5:
                    begin
                        tx_index    <= 4'd6;
                        spi_tx_data <= tx_b3;
                    end

                    4'd6:
                    begin
                        tx_index    <= 4'd7;
                        spi_tx_data <= tx_b4;
                    end

                    4'd7:
                    begin
                        tx_index    <= 4'd8;
                        spi_tx_data <= tx_b5;
                    end

                    default:
                    begin
                        tx_busy     <= 1'b0;
                        tx_index    <= 3'd0;
                        spi_tx_valid <= 1'b0;
                    end
                endcase
            end
        end
    end
end

endmodule
