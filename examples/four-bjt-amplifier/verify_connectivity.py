"""Compare logical project connectivity with a native flattened netlist.

Read-only on project/SCM/netlist sources. No FASTMEAN or UI launch. This does
not use layout, SCM wire union-find, preview geometry, or native node numbers
as an oracle for intended connectivity: intent comes from project JSON only.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DEFAULT_SPEC=ROOT/'project.input.json'
DEFAULT_NETLIST=ROOT/'native-netlist.txt'
COUNTS={'R':2,'C':2,'L':2,'D':2,'U':2,'V':2,'I':2,'G':4,'E':4,'F':4,
        'VCCS':4,'VCVS':4,'CCCS':4,'DIODE':2}
ALIASES={'V':'U','VCCS':'G','VCVS':'E','CCCS':'F','DIODE':'D','SUB':'X'}

class Union:
    def __init__(self):self.parent={}
    def find(self,token):
        self.parent.setdefault(token,token)
        if self.parent[token]!=token:self.parent[token]=self.find(self.parent[token])
        return self.parent[token]
    def join(self,left,right):self.parent[self.find(left)]=self.find(right)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def flatten_expected(spec):
    union=Union();components={};terminals={};net_tokens={}
    models=spec.get('models',{})
    def net(scope,label):
        label=str(label)
        token=('net','',label) if label=='0' else ('net',scope,label)
        net_tokens[token]=('0' if label=='0' else scope+'.'+label if scope else label)
        return token
    def walk(circuit,scope,active):
        for component in circuit['components']:
            name=(scope+'.' if scope else '')+component['name']
            kind=component.get('kind',component.get('type','')).upper();kind=ALIASES.get(kind,kind)
            if kind=='X':
                model=component['model']
                if model in active:raise ValueError('Cyclic logical model reference: '+model)
                definition=models[model];child=definition['circuit']
                ports=child.get('ports',{})
                if isinstance(ports,list):ports={label:label for label in ports}
                if set(component['connections'])!=set(ports):raise ValueError('Exposed model ports disagree for '+name)
                for pin,parent_net in component['connections'].items():
                    union.join(net(scope,parent_net),net(name,ports[pin]))
                walk(child,name,(*active,model))
            else:
                if name in components:raise ValueError('Duplicate flattened component '+name)
                nodes=list(component['nodes'])
                if kind not in COUNTS or len(nodes)!=COUNTS[kind]:raise ValueError('Unsupported terminal count for '+name)
                if kind=='U':nodes.reverse()  # public voltage source [+,-], native [-,+]
                components[name]={'kind':kind,'count':len(nodes)}
                for pin,label in enumerate(nodes,1):
                    terminal=(name,pin);token=('terminal',name,pin)
                    terminals[terminal]=token;union.join(token,net(scope,label))
    walk(spec['circuit'],'',())
    partitions=collections.defaultdict(set);labels=collections.defaultdict(set)
    for terminal,token in terminals.items():partitions[union.find(token)].add(terminal)
    for token,label in net_tokens.items():labels[union.find(token)].add(label)
    terminal_group={terminal:root for root,group in partitions.items() for terminal in group}
    return {'components':components,'partitions':dict(partitions),'labels':dict(labels),'terminal_group':terminal_group}

def parse_native(path,components):
    content=path.read_bytes()
    try:text=content.decode('utf8')
    except UnicodeDecodeError:text=content.decode('cp1251')
    actual={};extra=[];ports={}
    for lineno,line in enumerate(text.splitlines(),1):
        parts=line.split()
        if not parts or parts[0].startswith(('*',';','.')):continue
        name=parts[0]
        if name in components:
            if name in actual:raise ValueError(f'Duplicate native component {name} at line{lineno}')
            count=components[name]['count']
            if len(parts)<count+2 or not all(re.fullmatch(r'\d+',p) for p in parts[1:count+1]):
                raise ValueError(f'Malformed native terminals for {name}: {line}')
            actual[name]=parts[1:count+1]
        elif len(parts)==2 and re.fullmatch(r'\d+',parts[1]):ports[name]=parts[1]
        elif len(parts)>=4 and all(re.fullmatch(r'\d+',p) for p in parts[1:3]):
            extra.append({'line':lineno,'text':line})
    partitions=collections.defaultdict(set);terminal_node={}
    for name,nodes in actual.items():
        for pin,node in enumerate(nodes,1):
            terminal=(name,pin);partitions[node].add(terminal);terminal_node[terminal]=node
    return {'components':actual,'partitions':dict(partitions),'terminal_node':terminal_node,'unknown_components':extra,'ports':ports}

def display(terminals):return [f'{name}:{pin}' for name,pin in sorted(terminals)]

def audit(spec_path,netlist_path):
    spec=json.loads(spec_path.read_text(encoding='utf8'));expected=flatten_expected(spec)
    actual=parse_native(netlist_path,expected['components'])
    missing=sorted(set(expected['components'])-set(actual['components']))
    split=[];merge=[]
    for root,group in expected['partitions'].items():
        pieces=collections.defaultdict(set)
        for terminal in group:pieces[actual['terminal_node'].get(terminal,'MISSING')].add(terminal)
        if len(pieces)>1:
            split.append({'expected_net_labels':sorted(expected['labels'].get(root,())),
                'expected_terminals':display(group),'native_fragments':[
                    {'native_node':node,'terminals':display(ends)} for node,ends in sorted(pieces.items())]})
    for node,group in actual['partitions'].items():
        pieces=collections.defaultdict(set)
        for terminal in group:pieces[expected['terminal_group'][terminal]].add(terminal)
        if len(pieces)>1:
            merge.append({'native_node':node,'native_terminals':display(group),
                'merged_expected_nets':[{'expected_net_labels':sorted(expected['labels'].get(root,())),
                    'terminals':display(ends)} for root,ends in pieces.items()]})
    expected_sets={frozenset(group) for group in expected['partitions'].values()}
    actual_sets={frozenset(group) for group in actual['partitions'].values()}
    ok=not missing and not actual['unknown_components'] and expected_sets==actual_sets
    return {'ok':ok,'oracle':'Logical project JSON recursively flattened; native netlist compared as partitions of scoped (leaf component,pin) terminals. Native node numbers do not define expected nets.',
        'project_spec_path':spec_path.name,'project_spec_sha256':digest(spec_path),
        'native_netlist_path':netlist_path.name,'native_netlist_sha256':digest(netlist_path),
        'expected_components':len(expected['components']),'native_components':len(actual['components']),
        'expected_terminal_count':sum(c['count'] for c in expected['components'].values()),
        'expected_net_count':len(expected_sets),'native_net_count':len(actual_sets),
        'matching_partition_count':len(expected_sets & actual_sets),'missing_components':missing,
        'unknown_native_components':actual['unknown_components'],'split_expected_nets':split,'merged_expected_nets':merge}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--spec',type=Path,default=DEFAULT_SPEC)
    parser.add_argument('--netlist',type=Path,default=DEFAULT_NETLIST)
    parser.add_argument('--report',type=Path,default=ROOT/'connectivity-audit.json')
    args=parser.parse_args()
    netlist=args.netlist
    report=audit(args.spec.resolve(),netlist.resolve())
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'ok':report['ok'],'components':report['native_components'],'terminals':report['expected_terminal_count'],
        'expected_nets':report['expected_net_count'],'native_nets':report['native_net_count'],
        'splits':len(report['split_expected_nets']),'merges':len(report['merged_expected_nets']),
        'report':str(args.report)},indent=2))
    return 0 if report['ok'] else 1

if __name__=='__main__':raise SystemExit(main())
