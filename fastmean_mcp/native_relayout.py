"""Layout catalogue primitives while retaining the original portable project."""
import copy
from .schematic import SchemeError,_summarize,read_scheme


def relayout_native(source_path,output_path,placements=None,density="compact"):
    from .annotations import _copy_circuit
    from .element_catalog import get_element
    from .layout import build_layout
    from .relayout import _map_connectivity, _analysis_strings, _U_CALL, _external_interfaces
    import re
    metadata={}
    def transform(document):
        body=document["scm"]
        before=_summarize(document,source_path,"utf-8")
        old=body["Scheme"].get("Objects") or []
        if any(obj.get("Type") in {410,420} for obj in old):
            raise SchemeError("Relayout of external DLL co-simulation contacts requires a validated plugin binding and is not supported.")
        for expression in _analysis_strings(body, [obj for obj in old if obj.get("Type")==900]):
            matches=list(_U_CALL.finditer(expression))
            if len(matches)!=len(re.findall(r"(?<![A-Za-z0-9_])U\s*\(",expression,re.I)):
                raise SchemeError("Complex nested U(...) references cannot be safely preserved during relayout.")
            if any(token.strip().isdecimal() and token.strip()!="0"
                   for match in matches for token in match[1].split(",")):
                raise SchemeError("Numeric node-voltage references cannot survive renumbering; add named ports before relayout.")
        by_id={obj["ID"]:obj for obj in old}
        components=[]
        for part in before["components"]:
            try:entry=get_element(part["native_type"])
            except KeyError as error:raise SchemeError(f"Relayout has unsupported native type {part['native_type']}.") from error
            if entry.get("internal"):raise SchemeError("Internal native auxiliary records cannot be laid out.")
            components.append({"kind":entry["kind"],"name":part["name"],"nodes":part["nodes"],
                "_native_nodes":part["native_pin_nodes"],"_native_type":part["native_type"],
                "_native_params":copy.deepcopy(by_id[part["native_id"]].get("Params") or {})})
        ports=before["ports"]
        if not ports:
            ports,_,_=_external_interfaces(before,body,[obj for obj in old if obj.get("Type")==900])
        output=next((name for name in ports if name.casefold() in {"out","output"}),next(iter(ports)))
        options={"output":output}
        input_name=next((name for name in ports if name.casefold() in {"in","input"}),None)
        if input_name:options["input"]=input_name
        layout=build_layout(components,ports,options,placements=placements,density=density)
        by_name={part["name"]:by_id[part["native_id"]] for part in before["components"]}
        objects=[]
        for obj in layout["objects"]:
            if obj.get("Name") in by_name and obj["Type"] not in {200,300,400,900}:
                restored=copy.deepcopy(by_name[obj["Name"]])
                for key in ("ID","X","Y","Rot","FlipH","FlipV"):restored[key]=obj[key]
                objects.append(restored)
            else:objects.append(obj)
        next_id=max(obj["ID"] for obj in objects)+1
        note_y=layout["bounds"][3]+120
        for obj in old:
            if obj["Type"]!=900:continue
            note=copy.deepcopy(obj)
            note.update(ID=next_id,X=layout["bounds"][0]+160,Y=note_y)
            next_id+=1
            note_y+=max(120,24*(str((note.get("Params") or {}).get("Text","")).count("\n")+1)+60)
            objects.append(note)
        body["Scheme"].update(Objects=objects,Wires=layout["wires"])
        general=body.setdefault("General",{})
        left,top,right,bottom=layout["bounds"]
        general.update(HPos=(left+right)//2,VPos=(top+bottom)//2,
                       Scale=max(15,min(100,int(100*min(850/max(right-left,1),600/max(bottom-top,1))))))
        general["SWidth"]=max(general.get("SWidth",3000),layout["bounds"][2]+500)
        general["SHeight"]=max(general.get("SHeight",3000),note_y+400)
        if any(part["kind"]=="X" for part in components):body.setdefault("General",{})["Scale"]=100
        after=_summarize(document,output_path,"utf-8")
        mapping=_map_connectivity(before,after)
        if any(after["ports"].get(alias)!=mapping.get(node) for alias,node in ports.items()):
            raise SchemeError("Native relayout changed an external interface.")
        metadata.update(node_mapping=mapping,external_ports=copy.deepcopy(after["ports"]),
                        preserved_analysis_sections=[key for key in ("TD","FD","AOD","SOD","DCOP") if key in body],
                        removed_internal_ports=[],layout={key:value for key,value in layout.items()
            if key not in {"objects","wires","component_ids"}})
    result=_copy_circuit(source_path,output_path,root_transform=transform)
    result={**read_scheme(result["path"]),**result}
    result.update(metadata,ok=True,preserved_analysis=True,
                  origin="Native catalogue layout; original component parameters and project retained")
    return result
