"""Shared engineering-preview caption positions and routing clearance.

These describe our preview, not undocumented native FASTMEAN text placement.
Controlled sources expose pins on both ends of an axis, so their captions go
beside that axis instead of over the outgoing terminal leads.
"""
from __future__ import annotations

from functools import lru_cache
import math


_LEGACY_CAPTION_TYPES = frozenset({1000,1001,1002,2010,3010,1101,6000,6001,6002,6101,6400,6600})
CAPTION_TYPES = _LEGACY_CAPTION_TYPES
from .element_catalog import entries as _catalog_entries
CAPTION_TYPES |= frozenset(entry["typeid"] for entry in _catalog_entries() if entry["kind"]!="X" and not entry.get("internal"))


def controlled_source_value(obj):
    """Match the preview's compact numeric controlled-source value label."""
    key,unit = {6000:("g","S"),6001:("k",""),6002:("h",""),6400:("k","")}[obj["Type"]]
    value = (obj.get("Params") or {}).get(key,0)
    if not isinstance(value,(int,float)) or isinstance(value,bool):
        return f"{key}={value} {unit}".rstrip()
    exponent = max(-12,min(12,3*math.floor(math.log10(abs(value))/3))) if value else 0
    prefix = {-12:"p",-9:"n",-6:"µ",-3:"m",0:"",3:"k",6:"M",9:"G",12:"T"}[exponent]
    return f"{key}={value/10**exponent:.3g} {prefix}{unit}".rstrip()


def _quantity(value,unit):
    if not isinstance(value,(int,float)) or isinstance(value,bool): return str(value)+" "+unit
    exponent = max(-12,min(12,3*math.floor(math.log10(abs(value))/3))) if value else 0
    prefix = {-12:"p",-9:"n",-6:"µ",-3:"m",0:"",3:"k",6:"M",9:"G",12:"T"}[exponent]
    return f"{value/10**exponent:.3g} {prefix}{unit}".rstrip()


def native_component_value(obj):
    tid = obj["Type"]
    params = obj.get("Params") or {}
    if tid in {1000,1001,1002}:
        key,unit = {1000:("R","Ω"),1001:("C","F"),1002:("L","H")}[tid]
        return _quantity(params.get(key),unit)
    if tid in {2010,3010}:
        key,unit = ("I","A") if tid == 3010 else ("U","V")
        mode = params.get("ST")
        if mode == 1: return _quantity((params.get("DC") or {}).get(key+"0"),unit)
        if mode == 2:
            ac = params.get("AC") or {}
            return "sine: "+_quantity(ac.get(key+"0"),unit)+" / "+_quantity(ac.get("F"),"Hz")
        if mode in {3,4}:
            pulse = params.get("PULSE" if mode==3 else "TRIANG") or {}
            return (("pulse: " if mode==3 else "triangle: ")+_quantity(pulse.get(key+"MIN"),unit)+" to "
                    +_quantity(pulse.get(key+"MAX"),unit)+" / "+_quantity(pulse.get("F"),"Hz"))
        if mode == 5:
            return "PWL: "+str(len(((params.get("USER") or {}).get(key) or {}).get("x") or []))+" points"
        raise ValueError("Source captions require a known native waveform mode.")
    if obj["Type"] == 1101:
        return "Uon="+_quantity(params.get("Uon",0),"V")+"; Ron="+_quantity(params.get("Ron",0),"Ω")
    if tid == 6101:
        return "n="+_quantity(params.get("n"),"")
    if tid == 6600:
        return "Uon="+_quantity(params.get("Uon"),"V")+"; Uoff="+_quantity(params.get("Uoff"),"V")
    if tid in {6000,6001,6002,6400}:
        return controlled_source_value(obj)
    return "; ".join(key+"="+(_quantity(value,"") if isinstance(value,(int,float)) else
                f"table({len(value.get('x',[]))})" if isinstance(value,dict) else
                "["+str(len(value))+" values]" if isinstance(value,list) else str(value))
                for key,value in list(params.items())[:3])


def controlled_source_captions(obj, value):
    """Return literal text, position and style for generated G/E/F captions."""
    if obj["Type"] not in {6000,6001,6002}: return []
    return native_component_captions(obj,value)


def native_component_captions(obj,value):
    """Match the engineering preview's captions for supported primitives."""
    if obj["Type"] not in CAPTION_TYPES: return []
    if obj["Type"] not in _LEGACY_CAPTION_TYPES:
        return _catalog_component_captions(obj,value)
    if obj["Type"] in {1000,1001,1002,2010,3010}:
        vertical = obj.get("Rot",0) in (1,3)
        x = obj["X"]+42 if vertical else obj["X"]
        y = obj["Y"]-12 if vertical else obj["Y"]-51
        return [{"text":str(obj.get("Name","")),"x":x,"y":y,
                 "ha":"left" if vertical else "center","fontsize":10,"fontweight":"bold"},
                {"text":str(value),"x":x,"y":y+24,
                 "ha":"left" if vertical else "center","fontsize":9,"fontweight":"normal"}]
    from .native_geometry import body_bounds
    left,top,right,bottom = body_bounds(obj)
    vertical = obj.get("Rot",0) in ((1,3) if obj["Type"] in {1101,6101,6400} else (0,2))
    if vertical:
        x,y,align = right+28,(top+bottom)/2-12,"left"
        value_y = y+24
    else:
        x,y,align = (left+right)/2,top-40,"center"
        value_y = top-18
    return [{"text":str(obj.get("Name","")),"x":x,"y":y,"ha":align,
             "fontsize":10,"fontweight":"bold"},
            {"text":str(value),"x":x,"y":value_y,"ha":align,
             "fontsize":8,"fontweight":"normal"}]


def _catalog_component_captions(obj,value):
    """Use a pin-free world side, including rotated and optional-pin symbols.

    Extents include terminals outside the body (notably TR3 windings). A
    four-sided symbol uses the upper-right corner, clear of every outward
    terminal ray. The router consumes these same caption rectangles.
    """
    from .native_geometry import body_bounds, pin_directions, pin_positions
    left,top,right,bottom = body_bounds(obj)
    pins, directions = pin_positions(obj), pin_directions(obj)
    # Generated routing reserves a twenty-unit straight lead at each pin.
    points = list(pins.values()) + [(x+20*directions[pin][0],y+20*directions[pin][1])
                                   for pin,(x,y) in pins.items()]
    left = min(left,*(x for x,y in points))
    right = max(right,*(x for x,y in points))
    top = min(top,*(y for x,y in points))
    bottom = max(bottom,*(y for x,y in points))
    occupied = set(directions.values())
    side = next((side for side in ((0,-1),(1,0),(0,1),(-1,0)) if side not in occupied),None)
    if side == (0,-1):
        x,y,align = (left+right)/2,top-44,"center"
    elif side == (1,0):
        x,y,align = right+16,(top+bottom)/2-12,"left"
    elif side == (0,1):
        x,y,align = (left+right)/2,bottom+24,"center"
    elif side == (-1,0):
        x,y,align = left-16,(top+bottom)/2-12,"right"
    else:
        x,y,align = right+16,top-44,"left"
    return [{"text":str(obj.get("Name","")),"x":x,"y":y,"ha":align,
             "fontsize":10,"fontweight":"bold"},
            {"text":str(value),"x":x,"y":y+22,"ha":align,
             "fontsize":8,"fontweight":"normal"}]


@lru_cache(maxsize=1024)
def _text_width(text, fontsize, fontweight):
    # Matplotlib ships DejaVu Sans. Measuring the same font used by the
    # engineering preview avoids hand-estimated width/character heuristics.
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    font = FontProperties(family="DejaVu Sans",weight=fontweight)
    if not text: return 0
    return TextPath((0,0),text,size=fontsize,prop=font,usetex=False).get_extents().width*96/72


def caption_bounds(caption, padding=4):
    """Return a conservative document-space text rectangle for the preview.

    preview.py scales font points by pixels_per_unit*96/dpi; one nominal point
    therefore occupies 96/72 document units independent of figure dimensions.
    """
    width = _text_width(caption["text"],caption["fontsize"],caption["fontweight"])
    height = caption["fontsize"]*96/72
    x,y = caption["x"],caption["y"]
    left = x if caption["ha"] == "left" else x-width if caption["ha"] == "right" else x-width/2
    return (math.floor(left-padding),math.floor(y-height/2-padding),
            math.ceil(left+width+padding),math.ceil(y+height/2+padding))
