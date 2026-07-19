// Fixed service router.
// The default build supports 256 slots.
// Top provides the service ID map.
// One request buffer and one response buffer.
module data_router
#(
    parameter integer NUM_SLOTS = 256
)
(
    input  wire                         clk,
    input  wire                         rst_n,

    // Service ID map, packed as slot0 in the low byte.
    input  wire [NUM_SLOTS*8-1:0]       slot_service_ids,
    input  wire [NUM_SLOTS-1:0]         slot_service_valid,

    // Request from protocol_parse.
    input  wire                         req_valid,
    output wire                         req_ready,
    input  wire [7:0]                  req_service_id,
    input  wire [3:0]                  req_msg_type,
    input  wire [31:0]                 req_payload,

    // Response into protocol_parse.
    output wire                        tx_frame_valid,
    input  wire                        tx_frame_ready,
    output wire [7:0]                  tx_server_id,
    output wire [31:0]                 tx_payload,
    output wire [3:0]                  tx_msg_type,

    // One-hot request fanout.
    output reg  [NUM_SLOTS-1:0]         slot_req_valid,
    output reg  [NUM_SLOTS*4-1:0]       slot_req_msg_type,
    output reg  [NUM_SLOTS*32-1:0]      slot_req_payload,

    // One-hot response fanin.
    input  wire [NUM_SLOTS-1:0]         slot_rsp_valid,
    input  wire [NUM_SLOTS*4-1:0]       slot_rsp_msg_type,
    input  wire [NUM_SLOTS*32-1:0]      slot_rsp_payload,

    // Debug.
    output wire                        router_busy,
    output reg                         router_error,
    output reg                         dbg_req_fire,
    output reg [7:0]                   dbg_req_slot,
    output reg                         dbg_rsp_fire,
    output reg [7:0]                   dbg_rsp_slot
);

function integer clog2;
    input integer value;
    integer tmp;
    begin
        tmp = value - 1;
        for(clog2 = 0; tmp > 0; clog2 = clog2 + 1)
            tmp = tmp >> 1;
        if(clog2 == 0)
            clog2 = 1;
    end
endfunction

localparam integer SLOT_BITS = clog2(NUM_SLOTS);
localparam [3:0] MSG_REQUEST = 4'h0;
localparam [3:0] MSG_ERROR   = 4'h3;
localparam [31:0] ERR_INVALID_SERVICE = 32'h0000_0001;
localparam [31:0] ERR_BAD_TYPE        = 32'h0000_0002;

reg                     req_pending;
reg [7:0]               req_service_id_r;
reg [3:0]               req_msg_type_r;
reg [31:0]              req_payload_r;

reg                     req_busy;
reg [SLOT_BITS-1:0]     active_slot;
reg [7:0]               active_service_id;

reg                     rsp_pending;
reg [7:0]               rsp_server_id_r;
reg [31:0]              rsp_payload_r;
reg [3:0]               rsp_msg_type_r;

reg found_match;
reg [SLOT_BITS-1:0] found_slot;
integer idx;

reg [3:0]  selected_rsp_msg_type;
reg [31:0] selected_rsp_payload;

always @*
begin
    found_match = 1'b0;
    found_slot  = {SLOT_BITS{1'b0}};

    for(idx = 0; idx < NUM_SLOTS; idx = idx + 1)
    begin
        if(!found_match &&
           slot_service_valid[idx] &&
           req_service_id_r == slot_service_ids[(idx*8) +: 8])
        begin
            found_match = 1'b1;
            found_slot  = idx[SLOT_BITS-1:0];
        end
    end
end

always @*
begin
    selected_rsp_msg_type = 4'h0;
    selected_rsp_payload  = 32'h0000_0000;

    if(req_busy)
    begin
        selected_rsp_msg_type = slot_rsp_msg_type[(active_slot*4) +: 4];
        selected_rsp_payload  = slot_rsp_payload[(active_slot*32) +: 32];
    end
end

assign req_ready      = !req_pending;
assign tx_frame_valid = rsp_pending;
assign tx_server_id   = rsp_server_id_r;
assign tx_payload     = rsp_payload_r;
assign tx_msg_type    = rsp_msg_type_r;
assign router_busy    = req_pending || req_busy || rsp_pending;

always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        req_pending        <= 1'b0;
        req_service_id_r   <= 8'h00;
        req_msg_type_r     <= 4'h0;
        req_payload_r      <= 32'h0000_0000;
        req_busy           <= 1'b0;
        active_slot        <= {SLOT_BITS{1'b0}};
        active_service_id  <= 8'h00;
        rsp_pending        <= 1'b0;
        rsp_server_id_r    <= 8'h00;
        rsp_payload_r      <= 32'h0000_0000;
        rsp_msg_type_r     <= 4'h0;
        slot_req_valid     <= {NUM_SLOTS{1'b0}};
        slot_req_msg_type  <= {NUM_SLOTS*4{1'b0}};
        slot_req_payload   <= {NUM_SLOTS*32{1'b0}};
        router_error       <= 1'b0;
        dbg_req_fire       <= 1'b0;
        dbg_req_slot       <= 8'h00;
        dbg_rsp_fire       <= 1'b0;
        dbg_rsp_slot       <= 8'h00;
    end
    else
    begin
        slot_req_valid    <= {NUM_SLOTS{1'b0}};
        slot_req_msg_type <= {NUM_SLOTS*4{1'b0}};
        slot_req_payload  <= {NUM_SLOTS*32{1'b0}};
        router_error      <= 1'b0;
        dbg_req_fire      <= 1'b0;
        dbg_req_slot      <= 8'h00;
        dbg_rsp_fire      <= 1'b0;
        dbg_rsp_slot      <= 8'h00;

        // Queue one request pulse.
        if(req_valid && req_ready)
        begin
            req_pending      <= 1'b1;
            req_service_id_r <= req_service_id;
            req_msg_type_r   <= req_msg_type;
            req_payload_r    <= req_payload;
        end

        // Hand response data to protocol_parse when it is ready.
        if(rsp_pending && tx_frame_ready)
        begin
            rsp_pending <= 1'b0;
        end

        // Capture the selected service response.
        if(req_busy && slot_rsp_valid[active_slot] && !rsp_pending)
        begin
            rsp_pending       <= 1'b1;
            rsp_server_id_r   <= active_service_id;
            rsp_msg_type_r    <= selected_rsp_msg_type;
            rsp_payload_r     <= selected_rsp_payload;
            req_busy          <= 1'b0;
            dbg_rsp_fire      <= 1'b1;
            dbg_rsp_slot      <= active_slot;
        end

        // Dispatch a buffered request when the router is idle.
        if(req_pending && !req_busy && !rsp_pending)
        begin
            if(req_msg_type_r != MSG_REQUEST)
            begin
                router_error     <= 1'b1;
                rsp_pending      <= 1'b1;
                rsp_server_id_r  <= req_service_id_r;
                rsp_msg_type_r    <= MSG_ERROR;
                rsp_payload_r     <= ERR_BAD_TYPE;
                req_pending       <= 1'b0;
            end
            else if(found_match)
            begin
                slot_req_valid[found_slot] <= 1'b1;
                slot_req_msg_type[(found_slot*4) +: 4] <= req_msg_type_r;
                slot_req_payload[(found_slot*32) +: 32] <= req_payload_r;
                req_busy          <= 1'b1;
                active_slot       <= found_slot;
                active_service_id <= req_service_id_r;
                req_pending       <= 1'b0;
                dbg_req_fire      <= 1'b1;
                dbg_req_slot      <= found_slot;
            end
            else
            begin
                router_error     <= 1'b1;
                rsp_pending      <= 1'b1;
                rsp_server_id_r  <= req_service_id_r;
                rsp_msg_type_r   <= MSG_ERROR;
                rsp_payload_r    <= ERR_INVALID_SERVICE;
                req_pending      <= 1'b0;
            end
        end
    end
end

endmodule
