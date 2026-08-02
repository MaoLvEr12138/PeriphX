// Small asynchronous FIFO for byte-oriented clock-domain crossing.
// Write and read pointers cross domains as Gray code; data does not cross as
// a synchronized multi-bit bus.
module async_fifo
#(
    parameter integer DATA_WIDTH = 8,
    parameter integer ADDR_WIDTH = 3
)
(
    input  wire                  wr_clk,
    input  wire                  wr_rst_n,
    input  wire                  wr_en,
    input  wire [DATA_WIDTH-1:0] wr_data,
    output wire                  wr_full,
    output wire                  wr_ready,

    input  wire                  rd_clk,
    input  wire                  rd_rst_n,
    input  wire                  rd_en,
    output wire [DATA_WIDTH-1:0] rd_data,
    output wire                  rd_empty,
    output wire                  rd_valid
);

localparam integer DEPTH = (1 << ADDR_WIDTH);

reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];

reg [ADDR_WIDTH:0] wr_ptr_bin;
reg [ADDR_WIDTH:0] wr_ptr_gray;
reg [ADDR_WIDTH:0] rd_ptr_bin;
reg [ADDR_WIDTH:0] rd_ptr_gray;

reg [ADDR_WIDTH:0] rd_ptr_gray_wr_sync1;
reg [ADDR_WIDTH:0] rd_ptr_gray_wr_sync2;
reg [ADDR_WIDTH:0] wr_ptr_gray_rd_sync1;
reg [ADDR_WIDTH:0] wr_ptr_gray_rd_sync2;

wire wr_push;
wire rd_pop;
wire [ADDR_WIDTH:0] wr_ptr_bin_inc;
wire [ADDR_WIDTH:0] wr_ptr_gray_inc;
wire [ADDR_WIDTH:0] wr_ptr_bin_next;
wire [ADDR_WIDTH:0] wr_ptr_gray_next;
wire [ADDR_WIDTH:0] rd_ptr_bin_next;
wire [ADDR_WIDTH:0] rd_ptr_gray_next;
wire [ADDR_WIDTH:0] rd_ptr_gray_wr_full;

function [ADDR_WIDTH:0] bin_to_gray;
    input [ADDR_WIDTH:0] value;
    begin
        bin_to_gray = (value >> 1) ^ value;
    end
endfunction

assign wr_push = wr_en && !wr_full;
assign rd_pop = rd_en && !rd_empty;

assign wr_ptr_bin_inc = wr_ptr_bin + {{ADDR_WIDTH{1'b0}}, 1'b1};
assign wr_ptr_gray_inc = bin_to_gray(wr_ptr_bin_inc);
assign wr_ptr_bin_next = wr_ptr_bin + {{ADDR_WIDTH{1'b0}}, wr_push};
assign wr_ptr_gray_next = bin_to_gray(wr_ptr_bin_next);
assign rd_ptr_bin_next = rd_ptr_bin + {{ADDR_WIDTH{1'b0}}, rd_pop};
assign rd_ptr_gray_next = bin_to_gray(rd_ptr_bin_next);

assign rd_ptr_gray_wr_full = {
    ~rd_ptr_gray_wr_sync2[ADDR_WIDTH:ADDR_WIDTH-1],
    rd_ptr_gray_wr_sync2[ADDR_WIDTH-2:0]
};

assign wr_full = (wr_ptr_gray_inc == rd_ptr_gray_wr_full);
assign wr_ready = !wr_full;
assign rd_empty = (rd_ptr_gray == wr_ptr_gray_rd_sync2);
assign rd_valid = !rd_empty;
assign rd_data = mem[rd_ptr_bin[ADDR_WIDTH-1:0]];

always @(posedge wr_clk or negedge wr_rst_n)
begin
    if(!wr_rst_n)
    begin
        wr_ptr_bin  <= {ADDR_WIDTH+1{1'b0}};
        wr_ptr_gray <= {ADDR_WIDTH+1{1'b0}};
    end
    else
    begin
        if(wr_push)
        begin
            mem[wr_ptr_bin[ADDR_WIDTH-1:0]] <= wr_data;
            wr_ptr_bin  <= wr_ptr_bin_next;
            wr_ptr_gray <= wr_ptr_gray_next;
        end
    end
end

always @(posedge wr_clk or negedge wr_rst_n)
begin
    if(!wr_rst_n)
    begin
        rd_ptr_gray_wr_sync1 <= {ADDR_WIDTH+1{1'b0}};
        rd_ptr_gray_wr_sync2 <= {ADDR_WIDTH+1{1'b0}};
    end
    else
    begin
        rd_ptr_gray_wr_sync1 <= rd_ptr_gray;
        rd_ptr_gray_wr_sync2 <= rd_ptr_gray_wr_sync1;
    end
end

always @(posedge rd_clk or negedge rd_rst_n)
begin
    if(!rd_rst_n)
    begin
        rd_ptr_bin  <= {ADDR_WIDTH+1{1'b0}};
        rd_ptr_gray <= {ADDR_WIDTH+1{1'b0}};
    end
    else
    begin
        if(rd_pop)
        begin
            rd_ptr_bin  <= rd_ptr_bin_next;
            rd_ptr_gray <= rd_ptr_gray_next;
        end
    end
end

always @(posedge rd_clk or negedge rd_rst_n)
begin
    if(!rd_rst_n)
    begin
        wr_ptr_gray_rd_sync1 <= {ADDR_WIDTH+1{1'b0}};
        wr_ptr_gray_rd_sync2 <= {ADDR_WIDTH+1{1'b0}};
    end
    else
    begin
        wr_ptr_gray_rd_sync1 <= wr_ptr_gray;
        wr_ptr_gray_rd_sync2 <= wr_ptr_gray_rd_sync1;
    end
end

endmodule
