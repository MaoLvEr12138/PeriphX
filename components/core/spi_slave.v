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
reg [7:0] rx_byte_spi;  // SPI 域锁存的完整接收字节
reg rx_toggle_spi;      // SPI 域接收事件翻转标志，收满 1 字节后翻转

reg [7:0] tx_shift_spi; // SPI 域发送移位寄存器，当前正在从高位向外发送
reg [7:0] tx_stage_spi; // SPI 域下一发送字节暂存，用于字节边界重装载
reg [7:0] tx_load_spi;  // clk 域写入、SPI 域读取的待发送字节缓存
reg [2:0] tx_count_spi; // SPI 域发送 bit 计数，控制当前字节的移位节拍
// Marks the first byte after CS goes low.
reg tx_first_spi;       // SPI 域首字节标志，保证 CS 拉低后的第一个 MISO bit 稳定
reg tx_req_toggle;      // SPI 域发送请求翻转标志，在字节开始处通知 clk 域补数

//////////////////////////////////////////////////////
// CDC state
//////////////////////////////////////////////////////

reg rx_toggle_sync1;    // clk 域 RX toggle 第一级同步寄存器
reg rx_toggle_sync2;    // clk 域 RX toggle 第二级同步寄存器
reg rx_toggle_last;     // clk 域上一次 RX toggle 状态，用于边沿检测
reg rx_event_pending;   // clk 域接收事件待输出标志，延后一拍保证数据同步稳定
reg [7:0] rx_byte_sync1; // clk 域接收字节第一级同步寄存器
reg [7:0] rx_byte_sync2; // clk 域接收字节第二级同步寄存器

reg tx_req_sync1;       // clk 域 TX 请求 toggle 第一级同步寄存器
reg tx_req_sync2;       // clk 域 TX 请求 toggle 第二级同步寄存器
reg tx_req_last;        // clk 域上一次 TX 请求 toggle 状态，用于生成 tx_ready

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
            // 收满 8 bit 后锁存完整字节，并翻转事件标志通知 clk 域。
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

// Keep the next TX byte staged in the SPI domain.
// The first byte after CS uses the staged byte directly so Mode 0 sees a
// stable MSB on the first rising SCK edge.
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
        // CS 无效期间预装载发送字节，保证下一次 CS 拉低时首 bit 已经稳定。
        tx_count_spi <= 3'd7;
        tx_shift_spi  <= tx_load_spi;
        tx_stage_spi  <= tx_load_spi;
        tx_first_spi  <= 1'b1;
    end
    else if(tx_first_spi)
    begin
        // Consume the first byte on the first falling edge after CS low.
        // CS 拉低后的首个下降沿开始消耗首字节，后续 bit 继续在下降沿更新。
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
        // 每个下降沿刷新下一字节暂存，给字节边界重装载使用。
        tx_stage_spi <= tx_load_spi;

        if(tx_count_spi == 0)
        begin
            // 当前字节发送完成，在字节边界装载 staged byte。
            tx_count_spi <= 3'd7;
            // Reload the staged byte and start the next byte cadence.
            tx_shift_spi <= tx_stage_spi;
            tx_first_spi <= 1'b0;
        end
        else
        begin
            // 当前字节尚未发送完成，左移一位并继续输出下一 bit。
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
        // 未选中时输出高阻；首 bit 直接取 staged MSB，避免 Mode 0 首个采样沿前不稳定。
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
        // 上层提供新字节时锁存，SPI 域会在后续字节窗口取走。
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
        // 将 SPI 域的接收事件和接收字节同步到 clk 域。
        rx_toggle_sync1 <= rx_toggle_spi;
        rx_toggle_sync2 <= rx_toggle_sync1;
        rx_byte_sync1   <= rx_byte_spi;
        rx_byte_sync2   <= rx_byte_sync1;

        rx_valid <= 1'b0;

        if(rx_event_pending)
        begin
            // 事件确认后一拍输出接收字节，rx_valid 只保持一个 clk 周期。
            rx_data         <= rx_byte_sync2;
            rx_valid        <= 1'b1;
            rx_event_pending <= 1'b0;
        end

        if(rx_toggle_sync2 != rx_toggle_last)
        begin
            // 检测到 RX toggle 变化，说明 SPI 域已经收到一个完整字节。
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
