module hfe(input [63:0] din_data,
        input din_last,
        output din_ready,
        input din_valid,
        output [63:0] dout_data,
        output dout_last,
        input dout_ready,
        output dout_valid,
        output [63:0] headers_data,
        output headers_last,
        input headers_ready,
        output headers_valid
    );

    assign din_ready = 1'bx;
    assign dout_data = 64'bxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx;
    assign dout_last = 1'bx;
    assign dout_valid = 1'bx;
    assign headers_data = 64'bxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx;
    assign headers_last = 1'bx;
    assign headers_valid = 1'bx;
endmodule
module patternMatch(input [63:0] din_data,
        input din_last,
        output din_ready,
        input din_valid,
        output [63:0] match_data,
        output match_last,
        input match_ready,
        output match_valid
    );

    assign din_ready = 1'bx;
    assign match_data = 64'bxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx;
    assign match_last = 1'bx;
    assign match_valid = 1'bx;
endmodule
module filter(input [31:0] cfg_ar_addr,
        input [2:0] cfg_ar_prot,
        output cfg_ar_ready,
        input cfg_ar_valid,
        input [31:0] cfg_aw_addr,
        input [2:0] cfg_aw_prot,
        output cfg_aw_ready,
        input cfg_aw_valid,
        input cfg_b_ready,
        output [1:0] cfg_b_resp,
        output cfg_b_valid,
        output [63:0] cfg_r_data,
        input cfg_r_ready,
        output [1:0] cfg_r_resp,
        output cfg_r_valid,
        input [63:0] cfg_w_data,
        output cfg_w_ready,
        input [7:0] cfg_w_strb,
        input cfg_w_valid,
        input [63:0] din_data,
        input din_last,
        output din_ready,
        input din_valid,
        output [63:0] dout_data,
        output dout_last,
        input dout_ready,
        output dout_valid,
        input [63:0] headers_data,
        input headers_last,
        output headers_ready,
        input headers_valid,
        input [63:0] patternMatch_data,
        input patternMatch_last,
        output patternMatch_ready,
        input patternMatch_valid
    );

    assign cfg_ar_ready = 1'bx;
    assign cfg_aw_ready = 1'bx;
    assign cfg_b_resp = 2'bxx;
    assign cfg_b_valid = 1'bx;
    assign cfg_r_data = 64'bxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx;
    assign cfg_r_resp = 2'bxx;
    assign cfg_r_valid = 1'bx;
    assign cfg_w_ready = 1'bx;
    assign din_ready = 1'bx;
    assign dout_data = 64'bxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx;
    assign dout_last = 1'bx;
    assign dout_valid = 1'bx;
    assign headers_ready = 1'bx;
    assign patternMatch_ready = 1'bx;
endmodule
module exporter(input [63:0] din_data,
        input din_last,
        output din_ready,
        input din_valid,
        output [63:0] dout_data,
        output dout_last,
        input dout_ready,
        output dout_valid
    );

    assign din_ready = 1'bx;
    assign dout_data = 64'bxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx;
    assign dout_last = 1'bx;
    assign dout_valid = 1'bx;
endmodule
/*

    Stream duplicator for AxiStream interfaces
    
    :see: :class:`hwtLib.handshaked.splitCopy.HsSplitCopy`

    .. hwt-schematic::
    
*/
module gen_dout_splitCopy_0 #(parameter DATA_WIDTH = 64,
        parameter DEST_WIDTH = 0,
        parameter ID_WIDTH = 0,
        parameter INTF_CLS = "<class 'hwtLib.amba.axis.AxiStream'>",
        parameter IS_BIGENDIAN = 0,
        parameter OUTPUTS = 2,
        parameter USER_WIDTH = 0,
        parameter USE_KEEP = 0,
        parameter USE_STRB = 0
    )(input [63:0] dataIn_data,
        input dataIn_last,
        output reg dataIn_ready,
        input dataIn_valid,
        output [63:0] dataOut_0_data,
        output dataOut_0_last,
        input dataOut_0_ready,
        output reg dataOut_0_valid,
        output [63:0] dataOut_1_data,
        output dataOut_1_last,
        input dataOut_1_ready,
        output reg dataOut_1_valid
    );

    always @(dataOut_0_ready or dataOut_1_ready) begin: assig_process_dataIn_ready
        dataIn_ready = dataOut_0_ready & dataOut_1_ready;
    end

    assign dataOut_0_data = dataIn_data;
    assign dataOut_0_last = dataIn_last;
    always @(dataIn_valid or dataOut_1_ready) begin: assig_process_dataOut_0_valid
        dataOut_0_valid = dataIn_valid & dataOut_1_ready;
    end

    assign dataOut_1_data = dataIn_data;
    assign dataOut_1_last = dataIn_last;
    always @(dataIn_valid or dataOut_0_ready) begin: assig_process_dataOut_1_valid
        dataOut_1_valid = dataIn_valid & dataOut_0_ready;
    end

endmodule
/*

    This unit has actually no functionality it is just example
    of hierarchical design.

    .. hwt-schematic::
    
*/
module NetFilter #(parameter DATA_WIDTH = 64
    )(input [31:0] cfg_ar_addr,
        input [2:0] cfg_ar_prot,
        output cfg_ar_ready,
        input cfg_ar_valid,
        input [31:0] cfg_aw_addr,
        input [2:0] cfg_aw_prot,
        output cfg_aw_ready,
        input cfg_aw_valid,
        input cfg_b_ready,
        output [1:0] cfg_b_resp,
        output cfg_b_valid,
        output [63:0] cfg_r_data,
        input cfg_r_ready,
        output [1:0] cfg_r_resp,
        output cfg_r_valid,
        input [63:0] cfg_w_data,
        output cfg_w_ready,
        input [7:0] cfg_w_strb,
        input cfg_w_valid,
        input clk,
        input [63:0] din_data,
        input din_last,
        output din_ready,
        input din_valid,
        output [63:0] export_data,
        output export_last,
        input export_ready,
        output export_valid,
        input rst_n
    );

    wire [63:0] sig_exporter_din_data;
    wire sig_exporter_din_last;
    wire sig_exporter_din_ready;
    wire sig_exporter_din_valid;
    wire [63:0] sig_exporter_dout_data;
    wire sig_exporter_dout_last;
    wire sig_exporter_dout_ready;
    wire sig_exporter_dout_valid;
    wire [31:0] sig_filter_cfg_ar_addr;
    wire [2:0] sig_filter_cfg_ar_prot;
    wire sig_filter_cfg_ar_ready;
    wire sig_filter_cfg_ar_valid;
    wire [31:0] sig_filter_cfg_aw_addr;
    wire [2:0] sig_filter_cfg_aw_prot;
    wire sig_filter_cfg_aw_ready;
    wire sig_filter_cfg_aw_valid;
    wire sig_filter_cfg_b_ready;
    wire [1:0] sig_filter_cfg_b_resp;
    wire sig_filter_cfg_b_valid;
    wire [63:0] sig_filter_cfg_r_data;
    wire sig_filter_cfg_r_ready;
    wire [1:0] sig_filter_cfg_r_resp;
    wire sig_filter_cfg_r_valid;
    wire [63:0] sig_filter_cfg_w_data;
    wire sig_filter_cfg_w_ready;
    wire [7:0] sig_filter_cfg_w_strb;
    wire sig_filter_cfg_w_valid;
    wire [63:0] sig_filter_din_data;
    wire sig_filter_din_last;
    wire sig_filter_din_ready;
    wire sig_filter_din_valid;
    wire [63:0] sig_filter_dout_data;
    wire sig_filter_dout_last;
    wire sig_filter_dout_ready;
    wire sig_filter_dout_valid;
    wire [63:0] sig_filter_headers_data;
    wire sig_filter_headers_last;
    wire sig_filter_headers_ready;
    wire sig_filter_headers_valid;
    wire [63:0] sig_filter_patternMatch_data;
    wire sig_filter_patternMatch_last;
    wire sig_filter_patternMatch_ready;
    wire sig_filter_patternMatch_valid;
    wire [63:0] sig_gen_dout_splitCopy_0_dataIn_data;
    wire sig_gen_dout_splitCopy_0_dataIn_last;
    wire sig_gen_dout_splitCopy_0_dataIn_ready;
    wire sig_gen_dout_splitCopy_0_dataIn_valid;
    wire [63:0] sig_gen_dout_splitCopy_0_dataOut_0_data;
    wire sig_gen_dout_splitCopy_0_dataOut_0_last;
    wire sig_gen_dout_splitCopy_0_dataOut_0_ready;
    wire sig_gen_dout_splitCopy_0_dataOut_0_valid;
    wire [63:0] sig_gen_dout_splitCopy_0_dataOut_1_data;
    wire sig_gen_dout_splitCopy_0_dataOut_1_last;
    wire sig_gen_dout_splitCopy_0_dataOut_1_ready;
    wire sig_gen_dout_splitCopy_0_dataOut_1_valid;
    wire [63:0] sig_hfe_din_data;
    wire sig_hfe_din_last;
    wire sig_hfe_din_ready;
    wire sig_hfe_din_valid;
    wire [63:0] sig_hfe_dout_data;
    wire sig_hfe_dout_last;
    wire sig_hfe_dout_ready;
    wire sig_hfe_dout_valid;
    wire [63:0] sig_hfe_headers_data;
    wire sig_hfe_headers_last;
    wire sig_hfe_headers_ready;
    wire sig_hfe_headers_valid;
    wire [63:0] sig_patternMatch_din_data;
    wire sig_patternMatch_din_last;
    wire sig_patternMatch_din_ready;
    wire sig_patternMatch_din_valid;
    wire [63:0] sig_patternMatch_match_data;
    wire sig_patternMatch_match_last;
    wire sig_patternMatch_match_ready;
    wire sig_patternMatch_match_valid;
    exporter exporter_inst (.din_data(sig_exporter_din_data),
        .din_last(sig_exporter_din_last),
        .din_ready(sig_exporter_din_ready),
        .din_valid(sig_exporter_din_valid),
        .dout_data(sig_exporter_dout_data),
        .dout_last(sig_exporter_dout_last),
        .dout_ready(sig_exporter_dout_ready),
        .dout_valid(sig_exporter_dout_valid)
        );


    filter filter_inst (.cfg_ar_addr(sig_filter_cfg_ar_addr),
        .cfg_ar_prot(sig_filter_cfg_ar_prot),
        .cfg_ar_ready(sig_filter_cfg_ar_ready),
        .cfg_ar_valid(sig_filter_cfg_ar_valid),
        .cfg_aw_addr(sig_filter_cfg_aw_addr),
        .cfg_aw_prot(sig_filter_cfg_aw_prot),
        .cfg_aw_ready(sig_filter_cfg_aw_ready),
        .cfg_aw_valid(sig_filter_cfg_aw_valid),
        .cfg_b_ready(sig_filter_cfg_b_ready),
        .cfg_b_resp(sig_filter_cfg_b_resp),
        .cfg_b_valid(sig_filter_cfg_b_valid),
        .cfg_r_data(sig_filter_cfg_r_data),
        .cfg_r_ready(sig_filter_cfg_r_ready),
        .cfg_r_resp(sig_filter_cfg_r_resp),
        .cfg_r_valid(sig_filter_cfg_r_valid),
        .cfg_w_data(sig_filter_cfg_w_data),
        .cfg_w_ready(sig_filter_cfg_w_ready),
        .cfg_w_strb(sig_filter_cfg_w_strb),
        .cfg_w_valid(sig_filter_cfg_w_valid),
        .din_data(sig_filter_din_data),
        .din_last(sig_filter_din_last),
        .din_ready(sig_filter_din_ready),
        .din_valid(sig_filter_din_valid),
        .dout_data(sig_filter_dout_data),
        .dout_last(sig_filter_dout_last),
        .dout_ready(sig_filter_dout_ready),
        .dout_valid(sig_filter_dout_valid),
        .headers_data(sig_filter_headers_data),
        .headers_last(sig_filter_headers_last),
        .headers_ready(sig_filter_headers_ready),
        .headers_valid(sig_filter_headers_valid),
        .patternMatch_data(sig_filter_patternMatch_data),
        .patternMatch_last(sig_filter_patternMatch_last),
        .patternMatch_ready(sig_filter_patternMatch_ready),
        .patternMatch_valid(sig_filter_patternMatch_valid)
        );


    gen_dout_splitCopy_0 #(.DATA_WIDTH(64),
        .DEST_WIDTH(0),
        .ID_WIDTH(0),
        .INTF_CLS("<class 'hwtLib.amba.axis.AxiStream'>"),
        .IS_BIGENDIAN(0),
        .OUTPUTS(2),
        .USER_WIDTH(0),
        .USE_KEEP(0),
        .USE_STRB(0)
        ) gen_dout_splitCopy_0_inst (.dataIn_data(sig_gen_dout_splitCopy_0_dataIn_data),
        .dataIn_last(sig_gen_dout_splitCopy_0_dataIn_last),
        .dataIn_ready(sig_gen_dout_splitCopy_0_dataIn_ready),
        .dataIn_valid(sig_gen_dout_splitCopy_0_dataIn_valid),
        .dataOut_0_data(sig_gen_dout_splitCopy_0_dataOut_0_data),
        .dataOut_0_last(sig_gen_dout_splitCopy_0_dataOut_0_last),
        .dataOut_0_ready(sig_gen_dout_splitCopy_0_dataOut_0_ready),
        .dataOut_0_valid(sig_gen_dout_splitCopy_0_dataOut_0_valid),
        .dataOut_1_data(sig_gen_dout_splitCopy_0_dataOut_1_data),
        .dataOut_1_last(sig_gen_dout_splitCopy_0_dataOut_1_last),
        .dataOut_1_ready(sig_gen_dout_splitCopy_0_dataOut_1_ready),
        .dataOut_1_valid(sig_gen_dout_splitCopy_0_dataOut_1_valid)
        );


    hfe hfe_inst (.din_data(sig_hfe_din_data),
        .din_last(sig_hfe_din_last),
        .din_ready(sig_hfe_din_ready),
        .din_valid(sig_hfe_din_valid),
        .dout_data(sig_hfe_dout_data),
        .dout_last(sig_hfe_dout_last),
        .dout_ready(sig_hfe_dout_ready),
        .dout_valid(sig_hfe_dout_valid),
        .headers_data(sig_hfe_headers_data),
        .headers_last(sig_hfe_headers_last),
        .headers_ready(sig_hfe_headers_ready),
        .headers_valid(sig_hfe_headers_valid)
        );


    patternMatch patternMatch_inst (.din_data(sig_patternMatch_din_data),
        .din_last(sig_patternMatch_din_last),
        .din_ready(sig_patternMatch_din_ready),
        .din_valid(sig_patternMatch_din_valid),
        .match_data(sig_patternMatch_match_data),
        .match_last(sig_patternMatch_match_last),
        .match_ready(sig_patternMatch_match_ready),
        .match_valid(sig_patternMatch_match_valid)
        );


    assign cfg_ar_ready = sig_filter_cfg_ar_ready;
    assign cfg_aw_ready = sig_filter_cfg_aw_ready;
    assign cfg_b_resp = sig_filter_cfg_b_resp;
    assign cfg_b_valid = sig_filter_cfg_b_valid;
    assign cfg_r_data = sig_filter_cfg_r_data;
    assign cfg_r_resp = sig_filter_cfg_r_resp;
    assign cfg_r_valid = sig_filter_cfg_r_valid;
    assign cfg_w_ready = sig_filter_cfg_w_ready;
    assign din_ready = sig_hfe_din_ready;
    assign export_data = sig_exporter_dout_data;
    assign export_last = sig_exporter_dout_last;
    assign export_valid = sig_exporter_dout_valid;
    assign sig_exporter_din_data = sig_filter_dout_data;
    assign sig_exporter_din_last = sig_filter_dout_last;
    assign sig_exporter_din_valid = sig_filter_dout_valid;
    assign sig_exporter_dout_ready = export_ready;
    assign sig_filter_cfg_ar_addr = cfg_ar_addr;
    assign sig_filter_cfg_ar_prot = cfg_ar_prot;
    assign sig_filter_cfg_ar_valid = cfg_ar_valid;
    assign sig_filter_cfg_aw_addr = cfg_aw_addr;
    assign sig_filter_cfg_aw_prot = cfg_aw_prot;
    assign sig_filter_cfg_aw_valid = cfg_aw_valid;
    assign sig_filter_cfg_b_ready = cfg_b_ready;
    assign sig_filter_cfg_r_ready = cfg_r_ready;
    assign sig_filter_cfg_w_data = cfg_w_data;
    assign sig_filter_cfg_w_strb = cfg_w_strb;
    assign sig_filter_cfg_w_valid = cfg_w_valid;
    assign sig_filter_din_data = sig_gen_dout_splitCopy_0_dataOut_1_data;
    assign sig_filter_din_last = sig_gen_dout_splitCopy_0_dataOut_1_last;
    assign sig_filter_din_valid = sig_gen_dout_splitCopy_0_dataOut_1_valid;
    assign sig_filter_dout_ready = sig_exporter_din_ready;
    assign sig_filter_headers_data = sig_hfe_headers_data;
    assign sig_filter_headers_last = sig_hfe_headers_last;
    assign sig_filter_headers_valid = sig_hfe_headers_valid;
    assign sig_filter_patternMatch_data = sig_patternMatch_match_data;
    assign sig_filter_patternMatch_last = sig_patternMatch_match_last;
    assign sig_filter_patternMatch_valid = sig_patternMatch_match_valid;
    assign sig_gen_dout_splitCopy_0_dataIn_data = sig_hfe_dout_data;
    assign sig_gen_dout_splitCopy_0_dataIn_last = sig_hfe_dout_last;
    assign sig_gen_dout_splitCopy_0_dataIn_valid = sig_hfe_dout_valid;
    assign sig_gen_dout_splitCopy_0_dataOut_0_ready = sig_patternMatch_din_ready;
    assign sig_gen_dout_splitCopy_0_dataOut_1_ready = sig_filter_din_ready;
    assign sig_hfe_din_data = din_data;
    assign sig_hfe_din_last = din_last;
    assign sig_hfe_din_valid = din_valid;
    assign sig_hfe_dout_ready = sig_gen_dout_splitCopy_0_dataIn_ready;
    assign sig_hfe_headers_ready = sig_filter_headers_ready;
    assign sig_patternMatch_din_data = sig_gen_dout_splitCopy_0_dataOut_0_data;
    assign sig_patternMatch_din_last = sig_gen_dout_splitCopy_0_dataOut_0_last;
    assign sig_patternMatch_din_valid = sig_gen_dout_splitCopy_0_dataOut_0_valid;
    assign sig_patternMatch_match_ready = sig_filter_patternMatch_ready;
endmodule