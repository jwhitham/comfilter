
module microcode_store (clock_in, enable_in, uc_addr_in, uc_data_0);

    input clock_in;
    input enable_in;
    input [8:0] uc_addr_in;
    output [7:0] uc_data_0;

    wire one = 1'b1;
    wire zero = 1'b0;
    wire [8:0] unused_addr = 9'b0;
    wire [7:0] unused_data = 8'b0;
// wire [7:0] uc_data_0 = 8'b0;
SB_RAM512x8 ram512x8_inst (
.RDATA(uc_data_0),
.RADDR(uc_addr_in),
.RCLK(clock_in),
.RCLKE(one),
.RE(one),
.WADDR(unused_addr),
.WCLK(clock_in),
.WCLKE(one),
.WDATA(unused_data),
.WE(one));
defparam ram512x8_inst.INIT_0 = 256'h1F1E1D1C1B1A191817161514131211100F0E0D0C0B0A09080706050403020100;
defparam ram512x8_inst.INIT_1 = 256'h3F3E3D3C3B3A393837363534333231302F2E2D2C2B2A29282726252423222120;
defparam ram512x8_inst.INIT_2 = 256'h5F5E5D5C5B5A595857565554535251504F4E4D4C4B4A49484746454443424140;
defparam ram512x8_inst.INIT_3 = 256'h7F7E7D7C7B7A797877767574737271706F6E6D6C6B6A69686766656463626160;
defparam ram512x8_inst.INIT_4 = 256'h9F9E9D9C9B9A999897969594939291908F8E8D8C8B8A89888786858483828180;
defparam ram512x8_inst.INIT_5 = 256'hBFBEBDBCBBBAB9B8B7B6B5B4B3B2B1B0AFAEADACABAAA9A8A7A6A5A4A3A2A1A0;
defparam ram512x8_inst.INIT_6 = 256'hDFDEDDDCDBDAD9D8D7D6D5D4D3D2D1D0CFCECDCCCBCAC9C8C7C6C5C4C3C2C1C0;
defparam ram512x8_inst.INIT_7 = 256'hFFFEFDFCFBFAF9F8F7F6F5F4F3F2F1F0EFEEEDECEBEAE9E8E7E6E5E4E3E2E1E0;
defparam ram512x8_inst.INIT_8 = 256'h1F1E1D1C1B1A191817161514131211100F0E0D0C0B0A09080706050403020100;
defparam ram512x8_inst.INIT_9 = 256'h3F3E3D3C3B3A393837363534333231302F2E2D2C2B2A29282726252423222120;
defparam ram512x8_inst.INIT_A = 256'h5F5E5D5C5B5A595857565554535251504F4E4D4C4B4A49484746454443424140;
defparam ram512x8_inst.INIT_B = 256'h7F7E7D7C7B7A797877767574737271706F6E6D6C6B6A69686766656463626160;
defparam ram512x8_inst.INIT_C = 256'h9F9E9D9C9B9A999897969594939291908F8E8D8C8B8A89888786858483828180;
defparam ram512x8_inst.INIT_D = 256'hBFBEBDBCBBBAB9B8B7B6B5B4B3B2B1B0AFAEADACABAAA9A8A7A6A5A4A3A2A1A0;
defparam ram512x8_inst.INIT_E = 256'hDFDEDDDCDBDAD9D8D7D6D5D4D3D2D1D0CFCECDCCCBCAC9C8C7C6C5C4C3C2C1C0;
defparam ram512x8_inst.INIT_F = 256'hFFFEFDFCFBFAF9F8F7F6F5F4F3F2F1F0EFEEEDECEBEAE9E8E7E6E5E4E3E2E1E0;
// assign uc_data_out = uc_data_0;

endmodule
