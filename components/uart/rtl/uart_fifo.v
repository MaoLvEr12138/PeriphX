module uart_fifo
#(
    parameter integer DATA_WIDTH = 8,
    parameter integer ADDR_WIDTH = 4
)
(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  flush,
    input  wire                  wr_en,
    input  wire [DATA_WIDTH-1:0] wr_data,
    output wire                  full,
    input  wire                  rd_en,
    output wire [DATA_WIDTH-1:0] rd_data,
    output wire                  empty,
    output reg  [ADDR_WIDTH:0]   used_count
);

localparam [ADDR_WIDTH:0] DEPTH_COUNT = (1 << ADDR_WIDTH);

reg [DATA_WIDTH-1:0] mem [0:(1 << ADDR_WIDTH)-1];
reg [ADDR_WIDTH-1:0] wr_ptr;
reg [ADDR_WIDTH-1:0] rd_ptr;

wire do_write;
wire do_read;

assign full = (used_count == DEPTH_COUNT);
assign empty = (used_count == {ADDR_WIDTH+1{1'b0}});
assign do_write = wr_en && !full;
assign do_read = rd_en && !empty;
assign rd_data = mem[rd_ptr];

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        wr_ptr <= {ADDR_WIDTH{1'b0}};
        rd_ptr <= {ADDR_WIDTH{1'b0}};
        used_count <= {ADDR_WIDTH+1{1'b0}};
    end else if(flush) begin
        wr_ptr <= {ADDR_WIDTH{1'b0}};
        rd_ptr <= {ADDR_WIDTH{1'b0}};
        used_count <= {ADDR_WIDTH+1{1'b0}};
    end else begin
        if(do_write) begin
            mem[wr_ptr] <= wr_data;
            wr_ptr <= wr_ptr + {{ADDR_WIDTH-1{1'b0}}, 1'b1};
        end
        if(do_read) begin
            rd_ptr <= rd_ptr + {{ADDR_WIDTH-1{1'b0}}, 1'b1};
        end

        case({do_write, do_read})
            2'b10: used_count <= used_count + {{ADDR_WIDTH{1'b0}}, 1'b1};
            2'b01: used_count <= used_count - {{ADDR_WIDTH{1'b0}}, 1'b1};
            default: used_count <= used_count;
        endcase
    end
end

endmodule
