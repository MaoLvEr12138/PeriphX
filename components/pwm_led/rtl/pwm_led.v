module pwm_led (
    // 基础时序口
    input  wire        clk,           // 驱动时钟
    input  wire        rst_n,         // 全局复位（低电平有效）
    
    // 外部直接驱动的精简参数配置口（高效率并行输入）
    input  wire [31:0] sys_cnt_prds,  // 外部传入：PWM 完整周期内的时钟脉冲总数
    input  wire [31:0] sys_cnt_duty,  // 外部传入：PWM 单周期内高电平维持的时钟脉冲数
    
    // 物理输出口
    output reg         led_pwm        // 输出的 PWM 波形，直接驱动 LED 引脚
);

    // 内部唯一开销：一个用于周期循环的计数器
    reg [31:0] timer_cnt;

    // 1. 周期计数逻辑
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            timer_cnt <= 32'd0;
        end else if (timer_cnt >= sys_cnt_prds - 32'd1) begin
            timer_cnt <= 32'd0;
        end else begin
            timer_cnt <= timer_cnt + 32'd1;
        end
    end

    // 2. 占空比比对逻辑
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            led_pwm <= 1'b0;
        end else if (timer_cnt < sys_cnt_duty) begin
            led_pwm <= 1'b1;
        end else begin
            led_pwm <= 1'b0;
        end
    end

endmodule