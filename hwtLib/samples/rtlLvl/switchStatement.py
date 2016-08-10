from hdl_toolkit.hdlObjects.typeShortcuts import vecT, vec
from hdl_toolkit.serializer.formater import formatVhdl
from hdl_toolkit.synthesizer.codeOps import connect, Switch
from hdl_toolkit.synthesizer.rtlLevel.netlist import RtlNetlist


w = connect

if __name__ == "__main__":
    t = vecT(8)
    n = RtlNetlist("switchStatement")
    
    In = n.sig("input", t, defVal=8)
    Out = n.sig("output", t)
    
    Switch(In,
           *[(vec(i, 8), w(vec(i + 1, 8), Out)) for i in range(8)]
    )
    
    
    interf = [In, Out]
    
    for o in n.synthesize(interf):
            print(formatVhdl(str(o)))
