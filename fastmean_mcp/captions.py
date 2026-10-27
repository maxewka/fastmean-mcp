"""Shared engineering-preview caption positions and routing clearance.

These describe our preview, not undocumented native FASTMEAN text placement.
Controlled sources expose pins on both ends of an axis, so their captions go
beside that axis instead of over the outgoing terminal leads.
"""
from __future__ import annotations

from functools import lru_cache
import math


CAPTION_TYPES = frozenset({1000,1001,1002,2010,3010,1101,6000,6001,6002,6101,6600})


def controlled_source_value(obj):
    """Match the preview's compact numeric controlled-source value label."""
    key,unit = {6000:("g","S"),6001:("k",""),6002:("h","")}[obj["Type"]]
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
        if mode == 3:
            pulse = params.get("PULSE") or {}
            return ("pulse: "+_quantity(pulse.get(key+"MIN"),unit)+" to "
                    +_quantity(pulse.get(key+"MAX"),unit)+" / "+_quantity(pulse.get("F"),"Hz"))
        raise ValueError("Source captions require native DC, sine or pulse parameters.")
    if obj["Type"] == 1101:
        return "Uon="+_quantity(params.get("Uon",0),"V")+"; Ron="+_quantity(params.get("Ron",0),"Ω")
    if tid == 6101:
        return "n="+_quantity(params.get("n"),"")
    if tid == 6600:
        return "Uon="+_quantity(params.get("Uon"),"V")+"; Uoff="+_quantity(params.get("Uoff"),"V")
    return controlled_source_value(obj)


def controlled_source_captions(obj, value):
    """Return literal text, position and style for generated G/E/F captions."""
    if obj["Type"] not in {6000,6001,6002}: return []
    return native_component_captions(obj,value)


def native_component_captions(obj,value):
    """Match the engineering preview's captions for supported primitives."""
    if obj["Type"] not in CAPTION_TYPES: return []
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
    vertical = obj.get("Rot",0) in ((1,3) if obj["Type"] in {1101,6101} else (0,2))
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
