/* verilator lint_off UNUSED */
/* verilator lint_off SYNCASYNCNET */

// Byte-oriented SPI Mode 0 slave.
// RX captures bytes from the external master.
// TX stages the next byte in the clk domain and shifts it out on SCK.
module spi_slave
(
    input  wire clk,       // 系统时钟域，用于上层字节接口和跨时钟域同步
    input  wire rst_n,     // 低有效异步复位

    // SPI mode0
    input  wire spi_clk,   // SPI 主机提供的串行时钟
    input  wire spi_cs_n,  // SPI 片选信号，低有效
    input  wire spi_mosi,  // SPI 主机到从机的数据输入
    output wire spi_miso,  // SPI 从机到主机的数据输出，未选中时为高阻

    // RX
    output reg        rx_valid, // clk 域单周期接收有效脉冲
    output reg [7:0]  rx_data,  // clk 域输出的完整接收字节

    // TX
    input  wire       tx_valid, // clk 域输入的发送字节有效标志
    input  wire [7:0] tx_data,  // clk 域输入的待发送字节
    output reg        tx_ready, // clk 域单周期发送请求脉冲，提示上层准备下一个字节

    // CS
    output reg cs_active, // clk 域片选当前有效状态
    output reg cs_start,  // clk 域片选下降沿单周期脉冲
    output reg cs_end     // clk 域片选上升沿单周期脉冲
);

//////////////////////////////////////////////////////
// SPI clock domain
//////////////////////////////////////////////////////

reg [7:0] rx_shift_spi; // SPI 域接收移位寄存器，按上升沿移入 MOSI
reg [2:0] rx_count_spi; // SPI 域接收 bit 计数，0~7 表示一个字节内的位置

reg [7:0] tx_shift_spi; // SPI 域发送移位寄存器，当前正在从高位向外发送
reg [2:0] tx_count_spi; // SPI 域发送 bit 计数，控制当前字节的移位节拍
reg tx_miso_spi;        // SPI 域寄存后的 MISO 输出位
// Marks the first byte after CS goes low.
reg tx_first_spi;       // SPI 域首字节标志，保证 CS 拉低后的第一个 MISO bit 稳定
reg tx_req_toggle;      // SPI 域发送请求翻转标志，在字节开始处通知 clk 域补数

//////////////////////////////////////////////////////
// CDC state
//////////////////////////////////////////////////////

wire       rx_fifo_wr_en;    // SPI 域 RX FIFO 写使能
wire [7:0] rx_fifo_wr_data;  // SPI 域写入 RX FIFO 的完整接收字节
wire       rx_fifo_full;     // SPI 域 RX FIFO 满标志
wire       rx_fifo_ready;    // SPI 域 RX FIFO 可写标志
wire       rx_fifo_rd_en;    // clk 域 RX FIFO 读使能
wire [7:0] rx_fifo_rd_data;  // clk 域读取的 RX FIFO 队首字节
wire       rx_fifo_empty;    // clk 域 RX FIFO 空标志
wire       rx_fifo_valid;    // clk 域 RX FIFO 非空标志
wire       tx_fifo_wr_en;    // clk 域 TX FIFO 写使能
wire       tx_fifo_full;     // clk 域 TX FIFO 满标志
wire       tx_fifo_ready;    // clk 域 TX FIFO 可写标志
wire       tx_fifo_rd_clk;   // SPI 下降沿发送域对应的 FIFO 读时钟
wire       tx_fifo_rd_en;    // SPI 域 TX FIFO 读使能
wire [7:0] tx_fifo_rd_data;  // SPI 域读取的 TX FIFO 队首字节
wire       tx_fifo_empty;    // SPI 域 TX FIFO 空标志
wire       tx_fifo_valid;    // SPI 域 TX FIFO 非空标志

reg tx_req_sync1;       // clk 域 TX 请求 toggle 第一级同步寄存器
reg tx_req_sync2;       // clk 域 TX 请求 toggle 第二级同步寄存器
reg tx_req_last;        // clk 域上一次 TX 请求 toggle 状态，用于生成 tx_ready

assign rx_fifo_wr_data = {rx_shift_spi[6:0], spi_mosi};
assign rx_fifo_wr_en = (!spi_cs_n) && (rx_count_spi == 3'd7) && rx_fifo_ready;
assign rx_fifo_rd_en = rx_fifo_valid;
assign tx_fifo_wr_en = tx_valid && tx_fifo_ready;
assign tx_fifo_rd_clk = ~spi_clk;
assign tx_fifo_rd_en = (!spi_cs_n) && (tx_count_spi == 3'd0) && tx_fifo_valid;

async_fifo
#(
    .DATA_WIDTH(8),
    .ADDR_WIDTH(3)
)
u_rx_fifo
(
    .wr_clk   (spi_clk),
    .wr_rst_n (rst_n),
    .wr_en    (rx_fifo_wr_en),
    .wr_data  (rx_fifo_wr_data),
    .wr_full  (rx_fifo_full),
    .wr_ready (rx_fifo_ready),

    .rd_clk   (clk),
    .rd_rst_n (rst_n),
    .rd_en    (rx_fifo_rd_en),
    .rd_data  (rx_fifo_rd_data),
    .rd_empty (rx_fifo_empty),
    .rd_valid (rx_fifo_valid)
);

async_fifo
#(
    .DATA_WIDTH(8),
    .ADDR_WIDTH(3)
)
u_tx_fifo
(
    .wr_clk   (clk),
    .wr_rst_n (rst_n),
    .wr_en    (tx_fifo_wr_en),
    .wr_data  (tx_data),
    .wr_full  (tx_fifo_full),
    .wr_ready (tx_fifo_ready),

    .rd_clk   (tx_fifo_rd_clk),
    .rd_rst_n (rst_n),
    .rd_en    (tx_fifo_rd_en),
    .rd_data  (tx_fifo_rd_data),
    .rd_empty (tx_fifo_empty),
    .rd_valid (tx_fifo_valid)
);

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
    end
    else if(spi_cs_n)
    begin
        // CS 无效时丢弃未完成字节，下一次片选重新对齐 bit 计数。
        rx_shift_spi <= 8'h00;
        rx_count_spi <= 3'd0;
    end
    else
    begin
        // Mode 0 在 SCK 上升沿采样 MOSI，并按 MSB first 拼成字节。
        rx_shift_spi <= {
            rx_shift_spi[6:0],
            spi_mosi
        };

        if(rx_count_spi == 3'd7)
        begin
            // 收满 8 bit 后 RX FIFO 会在当前边沿写入完整字节。
            rx_count_spi <= 3'd0;
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

// Keep the next TX byte staged in the SPI domain.
// The first byte after CS uses the staged byte directly so Mode 0 sees a
// stable MSB on the first rising SCK edge.
always @(negedge spi_clk or posedge spi_cs_n or negedge rst_n)
begin
    if(!rst_n)
    begin
        tx_count_spi <= 3'd7;
        tx_shift_spi <= 8'h00;
        tx_miso_spi  <= 1'b0;
        tx_first_spi <= 1'b1;
    end
    else if(spi_cs_n)
    begin
        // CS 无效期间清空发送节拍状态，下一次片选重新对齐字节边界。
        tx_count_spi <= 3'd7;
        tx_shift_spi <= 8'h00;
        tx_miso_spi  <= 1'b0;
        tx_first_spi <= 1'b1;
    end
    else if(tx_first_spi)
    begin
        // CS 拉低后的首个下降沿先输出填充字节，等待 FIFO 指针跨域稳定。
        tx_count_spi <= 3'd6;
        tx_shift_spi <= tx_shift_spi;
        tx_miso_spi  <= tx_shift_spi[6];
        tx_first_spi <= 1'b0;
    end
    else
    begin
        if(tx_count_spi == 0)
        begin
            // 当前字节发送完成，在字节边界直接装载 FIFO 队首字节。
            tx_count_spi <= 3'd7;
            tx_shift_spi <= tx_fifo_valid ? tx_fifo_rd_data : 8'h00;
            tx_miso_spi  <= tx_fifo_valid ? tx_fifo_rd_data[7] : 1'b0;
            tx_first_spi <= 1'b0;
        end
        else
        begin
            // 当前字节尚未发送完成，仅推进 bit 计数并提前准备下一输出位。
            tx_count_spi <= tx_count_spi - 3'd1;
            tx_shift_spi <= tx_shift_spi;
            tx_miso_spi  <= tx_shift_spi[tx_count_spi - 3'd1];
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
        // 未选中时输出高阻；选中后输出下降沿提前准备好的寄存位。
        tx_miso_spi;

//////////////////////////////////////////////////////
// CDC RX
//////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        rx_valid <= 1'b0;
        rx_data  <= 8'h00;
    end
    else
    begin
        // RX FIFO 非空时每个 clk 周期输出并弹出一个完整接收字节。
        rx_valid <= 1'b0;

        if(rx_fifo_valid)
        begin
            rx_data  <= rx_fifo_rd_data;
            rx_valid <= 1'b1;
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
        // 同步 SPI 域的发送补数请求。
        tx_req_sync1 <= tx_req_toggle;
        tx_req_sync2 <= tx_req_sync1;

        tx_ready <= 1'b0;

        if(tx_req_sync2 != tx_req_last)
        begin
            // 每检测到一次 toggle 变化，就给上层一个字节窗口准备下一发送字节。
            tx_req_last <= tx_req_sync2;
            tx_ready    <= 1'b1;
        end
    end
end

//////////////////////////////////////////////////////
// TX request generation.
//
// Raise a byte-ready pulse at the start of a byte so the clk-domain bridge
// has a full byte window to settle the next value before the boundary.
//////////////////////////////////////////////////////

always @(posedge spi_clk or posedge spi_cs_n or negedge rst_n)
begin
    if(!rst_n)
    begin
        tx_req_toggle <= 1'b0;
    end
    else if(spi_cs_n)
    begin
        // CS 无效时清空发送请求状态，下一次事务重新开始补数字节节拍。
        tx_req_toggle <= 1'b0;
    end
    else if(tx_count_spi == 3'd7)
    begin
        // 字节开始处翻转请求标志，让 clk 域尽早准备下一个字节。
        tx_req_toggle <= ~tx_req_toggle;
    end
end

//////////////////////////////////////////////////////
// CS detect
//////////////////////////////////////////////////////

reg cs_last; // clk 域上一拍片选状态，用于检测 CS 边沿

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
        // 在 clk 域同步观察 CS 当前状态，并默认清除边沿脉冲。
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
