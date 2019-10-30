/*

    Basic d flip flop

    :attention: using this unit is pointless because HWToolkit can automatically
        generate such a register for any interface and datatype

    .. hwt-schematic::
    
*/
module DReg(input clk,
        input din,
        output dout,
        input rst
    );

    reg internReg = 1'b0;
    wire internReg_next;
    assign dout = internReg;
    always @(posedge clk) begin: assig_process_internReg
        if (rst == 1'b1) begin
            internReg <= 1'b0;
        end else begin
            internReg <= internReg_next;
        end
    end

    assign internReg_next = din;
endmodule