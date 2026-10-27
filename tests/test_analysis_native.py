"""Actual official-SDK/native checks for typed advanced analysis tools."""
import csv
import hashlib
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from fastmean_mcp.schematic import _load

APP = Path(os.environ.get("FASTMEAN_APP_DIR", ""))
if not (APP/"Fastmean.exe").is_file():
    APP = Path(os.environ.get("LOCALAPPDATA", ""))/"FASTMEAN 6.1"
ENABLED = (os.name == "nt" and os.environ.get("FASTMEAN_MCP_NATIVE_TEST") == "1"
           and (APP/"Fastmean.exe").is_file())


def rc(sine=False):
    source = {"kind":"U","name":"VIN","nodes":["input","0"],"value":1 if sine else 2}
    if sine:
        source["waveform"] = {"kind":"sine","frequency":1000,"phase":-90}
    return {"components":[source,
        {"kind":"R","name":"R1","nodes":["input","output"],"value":1000},
        {"kind":"C","name":"C1","nodes":["output","0"],"value":1e-6,"initial_condition":.3}],
        "ports":{"IN":"input","OUT":"output"}}


def data(result):
    with Path(result["csv_path"]).open(encoding="utf-8-sig",newline="") as stream:
        return [list(map(float,row)) for row in list(csv.reader(stream))[1:]]


@unittest.skipUnless(ENABLED,"Requires Windows FASTMEAN and FASTMEAN_MCP_NATIVE_TEST=1")
class AdvancedNativeTests(unittest.IsolatedAsyncioTestCase):
    async def session(self, action):
        with tempfile.TemporaryDirectory(prefix="fm-analysis-native-") as directory:
            params = StdioServerParameters(command=sys.executable,args=["-X","utf8","-m","fastmean_mcp"],
                env=dict(os.environ,FASTMEAN_APP_DIR=str(APP),FASTMEAN_OUTPUT_DIR=directory))
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer) as client:
                    await client.initialize()
                    async def call(tool,**arguments):
                        response = await client.call_tool(tool,arguments,read_timeout_seconds=90)
                        self.assertFalse(response.is_error,str(response.content)[:2400])
                        return response.structured_content
                    await call("fastmean_status")
                    await call("fastmean_example",kind="rc_lowpass")
                    await action(call)

    async def test_dc_commands_initial_conditions_and_saved_final_state(self):
        async def action(call):
            made = await call("fastmean_create_circuit",name="dc",spec=rc())
            path = Path(made["path"])
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            dc = await call("fastmean_dc",path=str(path),signals=["U(IN)","U(OUT)","I(R1)"])
            self.assertEqual(dc["values"],{"U(IN)":2.,"U(OUT)":2.,"I(R1)":0.})
            td = await call("fastmean_transient",path=str(path),signals=["U(OUT)","twice(U(OUT))*gain"],
                stop=.001,step=1e-5,sample_after=.0005,initial_conditions={"C1":.7},state2scheme=True,
                definitions=[{"name":"gain","expression":3},{"name":"twice","arguments":["x"],"expression":"2*x"}],
                overrides={"R1.R":2000})
            rows = data(td)
            self.assertGreaterEqual(rows[0][0],.0005)
            self.assertLess(max(abs(r[2]-6*r[1]) for r in rows),1e-11)
            _,final,_ = _load(td["final_state_path"])
            initial = next(o["Params"]["IC"] for o in final["scm"]["Scheme"]["Objects"] if o["Name"]=="C1")
            self.assertAlmostEqual(initial,rows[-1][1],delta=1e-10)  # Native SCM saves 12 significant digits.
            for mode,value in (("scheme",.3),("zero",0.),("dc",2.)):
                with self.subTest(mode=mode):
                    result = await call("fastmean_transient",path=str(path),signals=["U(OUT)"],
                        stop=1e-5,step=1e-6,initial_conditions=mode)
                    self.assertAlmostEqual(data(result)[0][1],value,delta=1e-12)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
        await self.session(action)

    async def test_native_sweep_harmonics_and_explicit_numpy_spectrum(self):
        async def action(call):
            made = await call("fastmean_create_circuit",name="sine",spec=rc(True))
            path = Path(made["path"])
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            ac = await call("fastmean_ac",path=str(path),signals=["RE(twice(U(OUT))*constant()/U(IN))"],
                fmin=10,fmax=1000,points=3,overrides={"R1.R":2000},definitions=[
                    {"name":"constant","arguments":[],"expression":3},
                    {"name":"twice","arguments":["x"],"expression":"2*x"}])
            for row in data(ac):
                self.assertAlmostEqual(row[1],6/(1+(2*math.pi*row[0]*.002)**2),delta=1e-12)
            sweep = await call("fastmean_sweep",path=str(path),target="R1.R",values=[500,1000,2000],
                analysis="ac",settings={"fmin":10,"fmax":1000,"points":3},signals=["MAG(U(OUT)/U(IN))"])
            for curve in sweep["curves"]:
                for row in data(curve):
                    expected = 1/math.sqrt(1+(2*math.pi*row[0]*curve["value"]*1e-6)**2)
                    self.assertAlmostEqual(row[1],expected,delta=1e-12)
            harmonics = await call("fastmean_harmonics",path=str(path),signal="U(IN)",frequencies=[1000,2000],
                window=[.005,.01],stop=.01,step=1e-6)
            self.assertGreater(harmonics["transient_row_count"],9000)
            self.assertAlmostEqual(harmonics["harmonics"][0]["magnitude"],1.,delta=1e-5)
            self.assertLess(harmonics["harmonics"][1]["magnitude"],1e-5)
            spectrum = await call("fastmean_spectrum",path=str(path),signal="U(IN)",window=[.005,.009],
                stop=.01,step=1e-6,points=1024,window_function="blackman")
            peak = max(data(spectrum)[1:],key=lambda row:row[1])
            self.assertAlmostEqual(peak[0],1000,delta=1e-9)
            self.assertAlmostEqual(peak[1],1.,delta=1e-4)
            self.assertIn("not native FFT",spectrum["origin"])
            summary = await call("fastmean_evaluate",path=str(path),signals=["rms(U(IN))","avg(U(IN))"],
                stop=.01,step=1e-6)
            self.assertAlmostEqual(summary["values"]["rms(U(IN))"],1/math.sqrt(2),delta=1e-6)
            self.assertAlmostEqual(summary["values"]["avg(U(IN))"],0.,delta=1e-6)
            native_fft = await call("fastmean_evaluate",path=str(path),signals=["MAG(FFT(U(IN)))"],
                stop=.01,step=1e-6,fft={"window":[.005,.009],"points":1024,"harmonics":40,"window_type":0})
            bins = data(native_fft)
            peak = max(bins[1:],key=lambda row:row[1])
            self.assertEqual(len(bins),41)
            self.assertAlmostEqual(peak[0],1000.,delta=1e-9)
            self.assertAlmostEqual(peak[1],1.,delta=1e-5)
            self.assertTrue(native_fft["native_fft"])
            summary_sweep = await call("fastmean_sweep",path=str(path),target="R1.R",values=[1000,2000],
                analysis="transient",settings={"stop":.01,"step":1e-6},
                signals=["last(R1.R)","last(avg(U(IN)^2))"])
            for index,row in enumerate(data(summary_sweep)):
                self.assertEqual(row[1],[1000,2000][index])
                self.assertAlmostEqual(row[2],.5,delta=1e-6)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
        await self.session(action)

    async def test_instance_initial_condition_does_not_change_a_shared_sibling_model(self):
        async def action(call):
            spec = {"models":{"CAP":{"pins":{"Left":["P"],"Right":["N"]},
                "circuit":{"components":[{"kind":"C","name":"C1","nodes":["p","n"],"value":1e-6,"initial_condition":.3}],
                    "ports":{"P":"p","N":"n"}}}},"circuit":{"components":[
                {"kind":"U","name":"VIN","nodes":["input","0"],"value":2},
                {"kind":"R","name":"R1","nodes":["input","a"],"value":1000},
                {"kind":"R","name":"R2","nodes":["input","b"],"value":1000},
                {"kind":"X","name":"FIRST","model":"CAP","connections":{"P":"a","N":"0"}},
                {"kind":"X","name":"SECOND","model":"CAP","connections":{"P":"b","N":"0"}}],
                "ports":{"OUTA":"a","OUTB":"b"}}}
            made = await call("fastmean_create_project",name="instance_ic",spec=spec)
            source = Path(made["path"])
            originals = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.parent.rglob("*.scm")}
            result = await call("fastmean_transient",path=str(source),signals=["U(OUTA)","U(OUTB)"],
                stop=1e-5,step=1e-6,initial_conditions={"FIRST.C1":.7})
            self.assertAlmostEqual(data(result)[0][1],.7,delta=1e-12)
            self.assertAlmostEqual(data(result)[0][2],.3,delta=1e-12)
            self.assertEqual(originals,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in originals})
        await self.session(action)
