"""Engineering symbols for the native catalogue, sharing exact pin anchors.

Functional devices use labeled IEC-style blocks when their native decorative
glyph is not reproduced. This is a drawing of the circuit, not a GUI capture.
"""
from __future__ import annotations

import math


def draw_catalog_symbol(axis,obj):
    from matplotlib.patches import Circle, Polygon, FancyArrowPatch
    from .element_catalog import get_element,get_geometry
    from .native_geometry import _transform
    entry=get_element(obj["Type"])
    geometry=get_geometry(obj["Type"],obj.get("Params"))
    pins=geometry["base_pin_positions"]
    directions=geometry["base_pin_directions"]
    left,top,right,bottom=geometry["body_bounds"]
    point=lambda x,y:_transform(obj,(x,y),translate=True)
    def line(a,b,**kwargs):
        axis.plot(*zip(point(*a),point(*b)),color="#161b22",linewidth=1.5,zorder=4,**kwargs)
    def label(text,x=0,y=0,size=8):
        xx,yy=point(x,y)
        axis.text(xx,yy,text,ha="center",va="center",fontsize=size,color="#161b22",zorder=8,parse_math=False)
    def arrow(a,b):
        axis.add_patch(FancyArrowPatch(point(*a),point(*b),arrowstyle="-|>",mutation_scale=8,
                                      linewidth=1.2,color="#161b22",zorder=6))
    def outline(vertices):
        axis.add_patch(Polygon([point(*p) for p in vertices],closed=True,facecolor="white",
                               edgecolor="#161b22",linewidth=1.5,zorder=4))
    def leads():
        for index,(x,y) in pins.items():
            dx,dy=directions[index]
            edge=(left if dx<0 else right,y) if dx else (x,top if dy<0 else bottom)
            line((x,y),edge)
    tid=obj["Type"]
    if tid in {410,420}:
        leads()
        outline([(-10,-7),(5,-7),(10,0),(5,7),(-10,7)])
        label(str(obj.get("Name","")),0,-18,9)
    elif tid==6102:
        for side,pair in ((-1,(1,2)),(1,(3,4)),(1,(5,6))):
            p,q=(pins[n] for n in pair)
            x=side*10
            a,b=p[1]+8,q[1]-8
            line(p,(x,p[1]));line((x,p[1]),(x,a))
            line(q,(x,q[1]));line((x,q[1]),(x,b))
            for i in range(4):
                center=a+(i+.5)*(b-a)/4
                half=(b-a)/8
                coil=[point(x-side*5*math.sin(math.pi*j/24),center-half*math.cos(math.pi*j/24)) for j in range(25)]
                axis.plot(*zip(*coil),color="#161b22",linewidth=1.5,zorder=4)
            axis.add_patch(Circle(point(x+side*4,a+2),1.7,facecolor="#161b22",edgecolor="none",zorder=6))
        for x in (-2,2):line((x,top),(x,bottom))
    elif tid==6300:
        line(pins[1],(-12,-8));line((-12,-18),(-12,4))
        line((-12,-14),(12,-8));line((12,-8),pins[3])
        line((-12,-2),(0,10));line((0,10),pins[2]);arrow((-8,2),(0,10))
    elif tid in {6200,6201,6615}:
        radius=min(right-left,bottom-top)/2-1
        axis.add_patch(Circle(point(0,0),radius,facecolor="white",edgecolor="#161b22",linewidth=1.4,zorder=4))
        if tid==6200:
            line(pins[1],(-8,0));line((-8,-12),(-8,12),linestyle="--")
            line(pins[2],(0,-12));line((-5,-12),(6,-12))
            line(pins[3],(-8,12));line((-8,12),(6,12))
        else:
            line(pins[1],(-10,8));line((-10,-8),(-10,10));line((0,-10),(0,10))
            line(pins[2],(8,-10));line((8,-10),(0,-10))
            line(pins[3],(8,10));line((8,10),(0,10));arrow((0,8),(-7,8))
    elif tid==6610:
        line(pins[1],(-10,0));line((6,0),pins[2])
        outline([(-10,-8),(-10,8),(6,0)])
        line((6,-10),(6,10));line(pins[3],(6,5))
    elif tid in {6910,6911,6912,6913}:
        outline([(left,top),(right,top),(right,bottom),(left,bottom)])
        params=obj.get("Params") or {}
        inverted={len(pins)} if tid==6910 or params.get("OutInv")==1 else set()
        inverted.update(index+1 for index,value in enumerate(params.get("InpInv") or []) if value==1)
        for index,(x,y) in pins.items():
            dx,dy=directions[index]
            edge=(left if dx<0 else right,y) if dx else (x,top if dy<0 else bottom)
            if index in inverted:
                line((x,y),(edge[0]+6*dx,edge[1]+6*dy))
                axis.add_patch(Circle(point(edge[0]+3*dx,edge[1]+3*dy),3,facecolor="white",
                    edgecolor="#161b22",linewidth=1.4,zorder=6))
            else:
                line((x,y),edge)
        label({6910:"1",6911:"&",6912:"≥1",6913:"=1"}[tid],size=8)
    elif tid==6800:
        nodes=[(-22,0),(0,-22),(22,0),(0,22)]
        for pin,node in zip((1,2,3,4),nodes):line(pins[pin],node)
        outline(nodes)
        # Four diode symbols occupy the bridge branches; outside conductors
        # still end at the real four native terminals.
        for a,b in ((nodes[0],nodes[1]),(nodes[2],nodes[1]),(nodes[3],nodes[0]),(nodes[3],nodes[2])):
            dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy);ux,uy=dx/length,dy/length
            cx,cy=(a[0]+b[0])/2,(a[1]+b[1])/2
            outline([(cx-3*ux-3*uy,cy-3*uy+3*ux),(cx-3*ux+3*uy,cy-3*uy-3*ux),(cx+3*ux,cy+3*uy)])
            line((cx+4*ux-4*uy,cy+4*uy+4*ux),(cx+4*ux+4*uy,cy+4*uy-4*ux))
    elif tid in {1003,1010,1011,1100,1110}:
        leads()
        if tid==1010:
            line((-3,top),(-3,bottom));line((3,top),(3,bottom))
            line((left,0),(-3,0));line((3,0),(right,0))
        elif tid==1011:
            wave=[point(left+(right-left)*j/64,-5*abs(math.sin(4*math.pi*j/64))) for j in range(65)]
            axis.plot(*zip(*wave),color="#161b22",linewidth=1.5,zorder=4)
        elif tid==1110:
            line((left,0),(-5,0));line((-5,0),(6,-7));line((7,0),(right,0));label("f",0,top-4,7)
        else:
            outline([(left,top),(right,top),(right,bottom),(left,bottom)])
        if tid in {1010,1011,1100}:line((-5,bottom+3),(5,top-3))
    else:
        leads()
        outline([(left,top),(right,top),(right,bottom),(left,bottom)])
        text={6910:"1",6911:"&",6912:"≥1",6913:"=1",7000:"Σ",6920:"CMP",
              6615:"MOS",6610:"SCR",6100:"GYR",6500:"PWM",6501:"PAM1",6502:"PAM2",6510:"×"}.get(tid,entry["kind"])
        label(text,size=8)
        for index,anchor in pins.items():
            dx,dy=directions[index]
            x,y=anchor[0]-dx*12,anchor[1]-dy*12
            label(str(index),x,y,6)
