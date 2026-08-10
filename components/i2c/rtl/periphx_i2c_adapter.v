module periphx_i2c_adapter #(
    parameter integer DEFAULT_CLK_DIV = 250,
    parameter integer DEFAULT_STRETCH_TIMEOUT = 1024,
    parameter integer BUFFER_DEPTH = 16
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        set_clk_div_req_valid,
    input  wire [3:0]  set_clk_div_req_msg_type,
    input  wire [31:0] set_clk_div_req_payload,
    output reg         set_clk_div_rsp_valid,
    output reg  [3:0]  set_clk_div_rsp_msg_type,
    output reg  [31:0] set_clk_div_rsp_payload,

    input  wire        set_stretch_timeout_req_valid,
    input  wire [3:0]  set_stretch_timeout_req_msg_type,
    input  wire [31:0] set_stretch_timeout_req_payload,
    output reg         set_stretch_timeout_rsp_valid,
    output reg  [3:0]  set_stretch_timeout_rsp_msg_type,
    output reg  [31:0] set_stretch_timeout_rsp_payload,

    input  wire        set_dev_addr_req_valid,
    input  wire [3:0]  set_dev_addr_req_msg_type,
    input  wire [31:0] set_dev_addr_req_payload,
    output reg         set_dev_addr_rsp_valid,
    output reg  [3:0]  set_dev_addr_rsp_msg_type,
    output reg  [31:0] set_dev_addr_rsp_payload,

    input  wire        set_reg_addr_req_valid,
    input  wire [3:0]  set_reg_addr_req_msg_type,
    input  wire [31:0] set_reg_addr_req_payload,
    output reg         set_reg_addr_rsp_valid,
    output reg  [3:0]  set_reg_addr_rsp_msg_type,
    output reg  [31:0] set_reg_addr_rsp_payload,

    input  wire        set_length_req_valid,
    input  wire [3:0]  set_length_req_msg_type,
    input  wire [31:0] set_length_req_payload,
    output reg         set_length_rsp_valid,
    output reg  [3:0]  set_length_rsp_msg_type,
    output reg  [31:0] set_length_rsp_payload,

    input  wire        push_write_data_req_valid,
    input  wire [3:0]  push_write_data_req_msg_type,
    input  wire [31:0] push_write_data_req_payload,
    output reg         push_write_data_rsp_valid,
    output reg  [3:0]  push_write_data_rsp_msg_type,
    output reg  [31:0] push_write_data_rsp_payload,

    input  wire        start_write_req_valid,
    input  wire [3:0]  start_write_req_msg_type,
    input  wire [31:0] start_write_req_payload,
    output reg         start_write_rsp_valid,
    output reg  [3:0]  start_write_rsp_msg_type,
    output reg  [31:0] start_write_rsp_payload,

    input  wire        start_read_req_valid,
    input  wire [3:0]  start_read_req_msg_type,
    input  wire [31:0] start_read_req_payload,
    output reg         start_read_rsp_valid,
    output reg  [3:0]  start_read_rsp_msg_type,
    output reg  [31:0] start_read_rsp_payload,

    input  wire        pop_read_data_req_valid,
    input  wire [3:0]  pop_read_data_req_msg_type,
    input  wire [31:0] pop_read_data_req_payload,
    output reg         pop_read_data_rsp_valid,
    output reg  [3:0]  pop_read_data_rsp_msg_type,
    output reg  [31:0] pop_read_data_rsp_payload,

    input  wire        get_status_req_valid,
    input  wire [3:0]  get_status_req_msg_type,
    input  wire [31:0] get_status_req_payload,
    output reg         get_status_rsp_valid,
    output reg  [3:0]  get_status_rsp_msg_type,
    output reg  [31:0] get_status_rsp_payload,

    input  wire        clear_status_req_valid,
    input  wire [3:0]  clear_status_req_msg_type,
    input  wire [31:0] clear_status_req_payload,
    output reg         clear_status_rsp_valid,
    output reg  [3:0]  clear_status_rsp_msg_type,
    output reg  [31:0] clear_status_rsp_payload,

    inout  wire        i2c_scl,
    inout  wire        i2c_sda
);

localparam [3:0] MSG_REQUEST  = 4'h0;
localparam [3:0] MSG_RESPONSE = 4'h1;
localparam [3:0] MSG_ERROR    = 4'h3;

localparam [31:0] RESP_OK      = 32'd0;
localparam [31:0] RESP_BUSY    = 32'd1;
localparam [31:0] RESP_INVALID = 32'd2;
localparam [31:0] RESP_FULL    = 32'd3;
localparam [31:0] RESP_EMPTY   = 32'd4;
localparam [31:0] ERR_BAD_TYPE = 32'h0000_0002;

localparam [31:0] STATUS_BUSY            = 32'h0000_0001;
localparam [31:0] STATUS_DONE            = 32'h0000_0002;
localparam [31:0] STATUS_ACK_ERROR       = 32'h0000_0004;
localparam [31:0] STATUS_STRETCH_TIMEOUT = 32'h0000_0008;
localparam [31:0] STATUS_ARB_LOST        = 32'h0000_0010;
localparam [31:0] STATUS_TX_FULL         = 32'h0000_0020;
localparam [31:0] STATUS_TX_EMPTY        = 32'h0000_0040;
localparam [31:0] STATUS_RX_FULL         = 32'h0000_0080;
localparam [31:0] STATUS_RX_EMPTY        = 32'h0000_0100;

localparam [3:0] ERR_NONE            = 4'd0;
localparam [3:0] ERR_INVALID_LENGTH  = 4'd7;
localparam [3:0] ERR_TX_UNDERFLOW    = 4'd8;
localparam [3:0] ERR_RX_OVERFLOW     = 4'd9;

reg [31:0] clk_div_r;
reg [31:0] stretch_timeout_r;
reg [6:0]  dev_addr_r;
reg [7:0]  reg_addr_r;
reg [7:0]  length_r;

reg        master_start;
reg        master_rw;
reg [127:0] master_tx_data;

wire       master_busy;
wire       master_done;
wire       master_read_valid;
wire [7:0] master_read_data;
wire [7:0] master_rx_count;
wire       master_ack_error;
wire       master_stretch_timeout_error;
wire       master_arb_lost;
wire [3:0] master_error_code;

reg [7:0] tx_mem0;
reg [7:0] tx_mem1;
reg [7:0] tx_mem2;
reg [7:0] tx_mem3;
reg [7:0] tx_mem4;
reg [7:0] tx_mem5;
reg [7:0] tx_mem6;
reg [7:0] tx_mem7;
reg [7:0] tx_mem8;
reg [7:0] tx_mem9;
reg [7:0] tx_mem10;
reg [7:0] tx_mem11;
reg [7:0] tx_mem12;
reg [7:0] tx_mem13;
reg [7:0] tx_mem14;
reg [7:0] tx_mem15;

reg [7:0] rx_mem0;
reg [7:0] rx_mem1;
reg [7:0] rx_mem2;
reg [7:0] rx_mem3;
reg [7:0] rx_mem4;
reg [7:0] rx_mem5;
reg [7:0] rx_mem6;
reg [7:0] rx_mem7;
reg [7:0] rx_mem8;
reg [7:0] rx_mem9;
reg [7:0] rx_mem10;
reg [7:0] rx_mem11;
reg [7:0] rx_mem12;
reg [7:0] rx_mem13;
reg [7:0] rx_mem14;
reg [7:0] rx_mem15;

reg [7:0] tx_count_r;
reg [7:0] rx_count_r;

reg        done_sticky;
reg        ack_error_sticky;
reg        stretch_timeout_sticky;
reg        arb_lost_sticky;
reg [3:0]  error_code_r;

wire       adapter_busy;
wire       tx_full;
wire       tx_empty;
wire       rx_full;
wire       rx_empty;
wire [31:0] status_payload;
wire [127:0] tx_snapshot;

assign adapter_busy = master_busy || master_start;
assign tx_full = (tx_count_r >= 8'd16);
assign tx_empty = (tx_count_r == 8'd0);
assign rx_full = (rx_count_r >= 8'd16);
assign rx_empty = (rx_count_r == 8'd0);
assign tx_snapshot = {tx_mem15, tx_mem14, tx_mem13, tx_mem12,
                      tx_mem11, tx_mem10, tx_mem9, tx_mem8,
                      tx_mem7, tx_mem6, tx_mem5, tx_mem4,
                      tx_mem3, tx_mem2, tx_mem1, tx_mem0};
assign status_payload =
    (adapter_busy ? STATUS_BUSY : 32'd0) |
    (done_sticky ? STATUS_DONE : 32'd0) |
    (ack_error_sticky ? STATUS_ACK_ERROR : 32'd0) |
    (stretch_timeout_sticky ? STATUS_STRETCH_TIMEOUT : 32'd0) |
    (arb_lost_sticky ? STATUS_ARB_LOST : 32'd0) |
    (tx_full ? STATUS_TX_FULL : 32'd0) |
    (tx_empty ? STATUS_TX_EMPTY : 32'd0) |
    (rx_full ? STATUS_RX_FULL : 32'd0) |
    (rx_empty ? STATUS_RX_EMPTY : 32'd0) |
    {rx_count_r, tx_count_r, error_code_r, 12'd0};

i2c_master #(
    .DEFAULT_CLK_DIV(DEFAULT_CLK_DIV),
    .DEFAULT_STRETCH_TIMEOUT(DEFAULT_STRETCH_TIMEOUT),
    .BUFFER_DEPTH(BUFFER_DEPTH)
) u_i2c_master (
    .clk                   (clk),
    .rst_n                 (rst_n),
    .start                 (master_start),
    .rw                    (master_rw),
    .dev_addr              (dev_addr_r),
    .reg_addr              (reg_addr_r),
    .length                (length_r),
    .tx_data               (master_tx_data),
    .clk_div               (clk_div_r),
    .stretch_timeout       (stretch_timeout_r),
    .busy                  (master_busy),
    .done                  (master_done),
    .read_valid            (master_read_valid),
    .read_data             (master_read_data),
    .rx_count              (master_rx_count),
    .ack_error             (master_ack_error),
    .stretch_timeout_error (master_stretch_timeout_error),
    .arb_lost              (master_arb_lost),
    .error_code            (master_error_code),
    .i2c_scl               (i2c_scl),
    .i2c_sda               (i2c_sda)
);

function [7:0] get_rx_front;
    input dummy;
    begin
        get_rx_front = rx_mem0;
    end
endfunction

always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
        clk_div_r <= 32'd0;
        stretch_timeout_r <= 32'd0;
        dev_addr_r <= 7'd0;
        reg_addr_r <= 8'd0;
        length_r <= 8'd1;
        master_start <= 1'b0;
        master_rw <= 1'b0;
        master_tx_data <= 128'd0;

        tx_mem0 <= 8'd0;
        tx_mem1 <= 8'd0;
        tx_mem2 <= 8'd0;
        tx_mem3 <= 8'd0;
        tx_mem4 <= 8'd0;
        tx_mem5 <= 8'd0;
        tx_mem6 <= 8'd0;
        tx_mem7 <= 8'd0;
        tx_mem8 <= 8'd0;
        tx_mem9 <= 8'd0;
        tx_mem10 <= 8'd0;
        tx_mem11 <= 8'd0;
        tx_mem12 <= 8'd0;
        tx_mem13 <= 8'd0;
        tx_mem14 <= 8'd0;
        tx_mem15 <= 8'd0;

        rx_mem0 <= 8'd0;
        rx_mem1 <= 8'd0;
        rx_mem2 <= 8'd0;
        rx_mem3 <= 8'd0;
        rx_mem4 <= 8'd0;
        rx_mem5 <= 8'd0;
        rx_mem6 <= 8'd0;
        rx_mem7 <= 8'd0;
        rx_mem8 <= 8'd0;
        rx_mem9 <= 8'd0;
        rx_mem10 <= 8'd0;
        rx_mem11 <= 8'd0;
        rx_mem12 <= 8'd0;
        rx_mem13 <= 8'd0;
        rx_mem14 <= 8'd0;
        rx_mem15 <= 8'd0;

        tx_count_r <= 8'd0;
        rx_count_r <= 8'd0;
        done_sticky <= 1'b0;
        ack_error_sticky <= 1'b0;
        stretch_timeout_sticky <= 1'b0;
        arb_lost_sticky <= 1'b0;
        error_code_r <= ERR_NONE;

        set_clk_div_rsp_valid <= 1'b0;
        set_clk_div_rsp_msg_type <= 4'd0;
        set_clk_div_rsp_payload <= 32'd0;
        set_stretch_timeout_rsp_valid <= 1'b0;
        set_stretch_timeout_rsp_msg_type <= 4'd0;
        set_stretch_timeout_rsp_payload <= 32'd0;
        set_dev_addr_rsp_valid <= 1'b0;
        set_dev_addr_rsp_msg_type <= 4'd0;
        set_dev_addr_rsp_payload <= 32'd0;
        set_reg_addr_rsp_valid <= 1'b0;
        set_reg_addr_rsp_msg_type <= 4'd0;
        set_reg_addr_rsp_payload <= 32'd0;
        set_length_rsp_valid <= 1'b0;
        set_length_rsp_msg_type <= 4'd0;
        set_length_rsp_payload <= 32'd0;
        push_write_data_rsp_valid <= 1'b0;
        push_write_data_rsp_msg_type <= 4'd0;
        push_write_data_rsp_payload <= 32'd0;
        start_write_rsp_valid <= 1'b0;
        start_write_rsp_msg_type <= 4'd0;
        start_write_rsp_payload <= 32'd0;
        start_read_rsp_valid <= 1'b0;
        start_read_rsp_msg_type <= 4'd0;
        start_read_rsp_payload <= 32'd0;
        pop_read_data_rsp_valid <= 1'b0;
        pop_read_data_rsp_msg_type <= 4'd0;
        pop_read_data_rsp_payload <= 32'd0;
        get_status_rsp_valid <= 1'b0;
        get_status_rsp_msg_type <= 4'd0;
        get_status_rsp_payload <= 32'd0;
        clear_status_rsp_valid <= 1'b0;
        clear_status_rsp_msg_type <= 4'd0;
        clear_status_rsp_payload <= 32'd0;
    end else begin
        master_start <= 1'b0;

        set_clk_div_rsp_valid <= 1'b0;
        set_clk_div_rsp_msg_type <= MSG_RESPONSE;
        set_clk_div_rsp_payload <= 32'd0;
        set_stretch_timeout_rsp_valid <= 1'b0;
        set_stretch_timeout_rsp_msg_type <= MSG_RESPONSE;
        set_stretch_timeout_rsp_payload <= 32'd0;
        set_dev_addr_rsp_valid <= 1'b0;
        set_dev_addr_rsp_msg_type <= MSG_RESPONSE;
        set_dev_addr_rsp_payload <= 32'd0;
        set_reg_addr_rsp_valid <= 1'b0;
        set_reg_addr_rsp_msg_type <= MSG_RESPONSE;
        set_reg_addr_rsp_payload <= 32'd0;
        set_length_rsp_valid <= 1'b0;
        set_length_rsp_msg_type <= MSG_RESPONSE;
        set_length_rsp_payload <= 32'd0;
        push_write_data_rsp_valid <= 1'b0;
        push_write_data_rsp_msg_type <= MSG_RESPONSE;
        push_write_data_rsp_payload <= 32'd0;
        start_write_rsp_valid <= 1'b0;
        start_write_rsp_msg_type <= MSG_RESPONSE;
        start_write_rsp_payload <= 32'd0;
        start_read_rsp_valid <= 1'b0;
        start_read_rsp_msg_type <= MSG_RESPONSE;
        start_read_rsp_payload <= 32'd0;
        pop_read_data_rsp_valid <= 1'b0;
        pop_read_data_rsp_msg_type <= MSG_RESPONSE;
        pop_read_data_rsp_payload <= 32'd0;
        get_status_rsp_valid <= 1'b0;
        get_status_rsp_msg_type <= MSG_RESPONSE;
        get_status_rsp_payload <= status_payload;
        clear_status_rsp_valid <= 1'b0;
        clear_status_rsp_msg_type <= MSG_RESPONSE;
        clear_status_rsp_payload <= 32'd0;

        if(set_clk_div_req_valid) begin
            set_clk_div_rsp_valid <= 1'b1;
            if(set_clk_div_req_msg_type != MSG_REQUEST) begin
                set_clk_div_rsp_msg_type <= MSG_ERROR;
                set_clk_div_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                set_clk_div_rsp_payload <= RESP_BUSY;
            end else begin
                clk_div_r <= set_clk_div_req_payload;
                set_clk_div_rsp_payload <= set_clk_div_req_payload;
            end
        end

        if(set_stretch_timeout_req_valid) begin
            set_stretch_timeout_rsp_valid <= 1'b1;
            if(set_stretch_timeout_req_msg_type != MSG_REQUEST) begin
                set_stretch_timeout_rsp_msg_type <= MSG_ERROR;
                set_stretch_timeout_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                set_stretch_timeout_rsp_payload <= RESP_BUSY;
            end else begin
                stretch_timeout_r <= set_stretch_timeout_req_payload;
                set_stretch_timeout_rsp_payload <= set_stretch_timeout_req_payload;
            end
        end

        if(set_dev_addr_req_valid) begin
            set_dev_addr_rsp_valid <= 1'b1;
            if(set_dev_addr_req_msg_type != MSG_REQUEST) begin
                set_dev_addr_rsp_msg_type <= MSG_ERROR;
                set_dev_addr_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                set_dev_addr_rsp_payload <= RESP_BUSY;
            end else begin
                dev_addr_r <= set_dev_addr_req_payload[6:0];
                set_dev_addr_rsp_payload <= {25'd0, set_dev_addr_req_payload[6:0]};
            end
        end

        if(set_reg_addr_req_valid) begin
            set_reg_addr_rsp_valid <= 1'b1;
            if(set_reg_addr_req_msg_type != MSG_REQUEST) begin
                set_reg_addr_rsp_msg_type <= MSG_ERROR;
                set_reg_addr_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                set_reg_addr_rsp_payload <= RESP_BUSY;
            end else begin
                reg_addr_r <= set_reg_addr_req_payload[7:0];
                set_reg_addr_rsp_payload <= {24'd0, set_reg_addr_req_payload[7:0]};
            end
        end

        if(set_length_req_valid) begin
            set_length_rsp_valid <= 1'b1;
            if(set_length_req_msg_type != MSG_REQUEST) begin
                set_length_rsp_msg_type <= MSG_ERROR;
                set_length_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                set_length_rsp_payload <= RESP_BUSY;
            end else if((set_length_req_payload[7:0] == 8'd0) ||
                        (set_length_req_payload[7:0] > 8'd16)) begin
                set_length_rsp_payload <= RESP_INVALID;
                ack_error_sticky <= 1'b1;
                error_code_r <= ERR_INVALID_LENGTH;
            end else begin
                length_r <= set_length_req_payload[7:0];
                set_length_rsp_payload <= RESP_OK;
            end
        end

        if(push_write_data_req_valid) begin
            push_write_data_rsp_valid <= 1'b1;
            if(push_write_data_req_msg_type != MSG_REQUEST) begin
                push_write_data_rsp_msg_type <= MSG_ERROR;
                push_write_data_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                push_write_data_rsp_payload <= RESP_BUSY;
            end else if(tx_full) begin
                push_write_data_rsp_payload <= RESP_FULL;
            end else begin
                case(tx_count_r[3:0])
                    4'd0:  tx_mem0 <= push_write_data_req_payload[7:0];
                    4'd1:  tx_mem1 <= push_write_data_req_payload[7:0];
                    4'd2:  tx_mem2 <= push_write_data_req_payload[7:0];
                    4'd3:  tx_mem3 <= push_write_data_req_payload[7:0];
                    4'd4:  tx_mem4 <= push_write_data_req_payload[7:0];
                    4'd5:  tx_mem5 <= push_write_data_req_payload[7:0];
                    4'd6:  tx_mem6 <= push_write_data_req_payload[7:0];
                    4'd7:  tx_mem7 <= push_write_data_req_payload[7:0];
                    4'd8:  tx_mem8 <= push_write_data_req_payload[7:0];
                    4'd9:  tx_mem9 <= push_write_data_req_payload[7:0];
                    4'd10: tx_mem10 <= push_write_data_req_payload[7:0];
                    4'd11: tx_mem11 <= push_write_data_req_payload[7:0];
                    4'd12: tx_mem12 <= push_write_data_req_payload[7:0];
                    4'd13: tx_mem13 <= push_write_data_req_payload[7:0];
                    4'd14: tx_mem14 <= push_write_data_req_payload[7:0];
                    4'd15: tx_mem15 <= push_write_data_req_payload[7:0];
                    default: tx_mem0 <= tx_mem0;
                endcase
                tx_count_r <= tx_count_r + 8'd1;
                push_write_data_rsp_payload <= RESP_OK;
            end
        end

        if(start_write_req_valid) begin
            start_write_rsp_valid <= 1'b1;
            if(start_write_req_msg_type != MSG_REQUEST) begin
                start_write_rsp_msg_type <= MSG_ERROR;
                start_write_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                start_write_rsp_payload <= RESP_BUSY;
            end else if((length_r == 8'd0) || (length_r > 8'd16)) begin
                start_write_rsp_payload <= RESP_INVALID;
                ack_error_sticky <= 1'b1;
                error_code_r <= ERR_INVALID_LENGTH;
            end else if(tx_count_r < length_r) begin
                start_write_rsp_payload <= RESP_EMPTY;
                ack_error_sticky <= 1'b1;
                error_code_r <= ERR_TX_UNDERFLOW;
            end else begin
                master_start <= 1'b1;
                master_rw <= 1'b0;
                master_tx_data <= tx_snapshot;
                start_write_rsp_payload <= RESP_OK;
            end
        end

        if(start_read_req_valid) begin
            start_read_rsp_valid <= 1'b1;
            if(start_read_req_msg_type != MSG_REQUEST) begin
                start_read_rsp_msg_type <= MSG_ERROR;
                start_read_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                start_read_rsp_payload <= RESP_BUSY;
            end else if((length_r == 8'd0) || (length_r > 8'd16)) begin
                start_read_rsp_payload <= RESP_INVALID;
                ack_error_sticky <= 1'b1;
                error_code_r <= ERR_INVALID_LENGTH;
            end else if((rx_count_r + length_r) > 8'd16) begin
                start_read_rsp_payload <= RESP_FULL;
                ack_error_sticky <= 1'b1;
                error_code_r <= ERR_RX_OVERFLOW;
            end else begin
                master_start <= 1'b1;
                master_rw <= 1'b1;
                master_tx_data <= tx_snapshot;
                start_read_rsp_payload <= RESP_OK;
            end
        end

        if(pop_read_data_req_valid) begin
            pop_read_data_rsp_valid <= 1'b1;
            if(pop_read_data_req_msg_type != MSG_REQUEST) begin
                pop_read_data_rsp_msg_type <= MSG_ERROR;
                pop_read_data_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                pop_read_data_rsp_payload <= RESP_BUSY;
            end else if(rx_empty) begin
                pop_read_data_rsp_payload <= RESP_EMPTY;
            end else begin
                pop_read_data_rsp_payload <= {24'd0, get_rx_front(1'b0)};
                rx_mem0 <= rx_mem1;
                rx_mem1 <= rx_mem2;
                rx_mem2 <= rx_mem3;
                rx_mem3 <= rx_mem4;
                rx_mem4 <= rx_mem5;
                rx_mem5 <= rx_mem6;
                rx_mem6 <= rx_mem7;
                rx_mem7 <= rx_mem8;
                rx_mem8 <= rx_mem9;
                rx_mem9 <= rx_mem10;
                rx_mem10 <= rx_mem11;
                rx_mem11 <= rx_mem12;
                rx_mem12 <= rx_mem13;
                rx_mem13 <= rx_mem14;
                rx_mem14 <= rx_mem15;
                rx_mem15 <= 8'd0;
                rx_count_r <= rx_count_r - 8'd1;
            end
        end

        if(get_status_req_valid) begin
            get_status_rsp_valid <= 1'b1;
            if(get_status_req_msg_type == MSG_REQUEST) begin
                get_status_rsp_payload <= status_payload;
            end else begin
                get_status_rsp_msg_type <= MSG_ERROR;
                get_status_rsp_payload <= ERR_BAD_TYPE;
            end
        end

        if(clear_status_req_valid) begin
            clear_status_rsp_valid <= 1'b1;
            if(clear_status_req_msg_type != MSG_REQUEST) begin
                clear_status_rsp_msg_type <= MSG_ERROR;
                clear_status_rsp_payload <= ERR_BAD_TYPE;
            end else if(adapter_busy) begin
                clear_status_rsp_payload <= RESP_BUSY;
            end else begin
                clear_status_rsp_payload <= RESP_OK;
                if(clear_status_req_payload == 32'd0) begin
                    done_sticky <= 1'b0;
                    ack_error_sticky <= 1'b0;
                    stretch_timeout_sticky <= 1'b0;
                    arb_lost_sticky <= 1'b0;
                    error_code_r <= ERR_NONE;
                    tx_count_r <= 8'd0;
                    rx_count_r <= 8'd0;
                end else begin
                    if(clear_status_req_payload[1]) begin
                        done_sticky <= 1'b0;
                    end
                    if(clear_status_req_payload[2]) begin
                        ack_error_sticky <= 1'b0;
                    end
                    if(clear_status_req_payload[3]) begin
                        stretch_timeout_sticky <= 1'b0;
                    end
                    if(clear_status_req_payload[4]) begin
                        arb_lost_sticky <= 1'b0;
                    end
                    if(clear_status_req_payload[8]) begin
                        tx_count_r <= 8'd0;
                    end
                    if(clear_status_req_payload[9]) begin
                        rx_count_r <= 8'd0;
                    end
                    if(clear_status_req_payload[15]) begin
                        error_code_r <= ERR_NONE;
                    end
                end
            end
        end

        if(master_read_valid) begin
            if(rx_count_r < 8'd16) begin
                case(rx_count_r[3:0])
                    4'd0:  rx_mem0 <= master_read_data;
                    4'd1:  rx_mem1 <= master_read_data;
                    4'd2:  rx_mem2 <= master_read_data;
                    4'd3:  rx_mem3 <= master_read_data;
                    4'd4:  rx_mem4 <= master_read_data;
                    4'd5:  rx_mem5 <= master_read_data;
                    4'd6:  rx_mem6 <= master_read_data;
                    4'd7:  rx_mem7 <= master_read_data;
                    4'd8:  rx_mem8 <= master_read_data;
                    4'd9:  rx_mem9 <= master_read_data;
                    4'd10: rx_mem10 <= master_read_data;
                    4'd11: rx_mem11 <= master_read_data;
                    4'd12: rx_mem12 <= master_read_data;
                    4'd13: rx_mem13 <= master_read_data;
                    4'd14: rx_mem14 <= master_read_data;
                    4'd15: rx_mem15 <= master_read_data;
                    default: rx_mem0 <= rx_mem0;
                endcase
                rx_count_r <= rx_count_r + 8'd1;
            end else begin
                ack_error_sticky <= 1'b1;
                error_code_r <= ERR_RX_OVERFLOW;
            end
        end

        if(master_done) begin
            done_sticky <= 1'b1;
            if(!master_rw && (master_error_code == ERR_NONE)) begin
                tx_count_r <= 8'd0;
            end
        end

        if(master_ack_error) begin
            ack_error_sticky <= 1'b1;
            error_code_r <= master_error_code;
        end

        if(master_stretch_timeout_error) begin
            stretch_timeout_sticky <= 1'b1;
            error_code_r <= master_error_code;
        end

        if(master_arb_lost) begin
            arb_lost_sticky <= 1'b1;
            error_code_r <= master_error_code;
        end
    end
end

endmodule
