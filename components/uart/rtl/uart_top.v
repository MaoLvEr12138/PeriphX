module uart_top(
	input 	sys_clk,	
	input 	sys_rst_n,	
 
	input 	uart_rxd,	
	output 	uart_txd	
 
);
parameter	UART_BPS=57600;			
parameter	CLK_FREQ=50_000_000;	
 
wire uart_en_w;
wire [7:0] uart_data_w; 


uart_tx#(
	.BPS		    (UART_BPS),
	.SYS_CLK_FRE	(CLK_FREQ))
u_uart_tx(
	.sys_clk		(sys_clk),
	.sys_rst_n	    (sys_rst_n),
	.uart_tx_en		(uart_en_w),
	.uart_data	    (uart_data_w),	
	.uart_txd	    (uart_txd)
);

uart_rx #(
	.BPS				(UART_BPS),
	.SYS_CLK_FRE		(CLK_FREQ))
u_uart_rx(
	.sys_clk			(sys_clk),
	.sys_rst_n		    (sys_rst_n),
	
	.uart_rxd		    (uart_rxd),	
	.uart_rx_done	    (uart_en_w),
	.uart_rx_data	    (uart_data_w)
);
 
endmodule
