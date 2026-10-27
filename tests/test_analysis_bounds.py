"""Hierarchy analysis stays cancellable and within private-project budgets."""
import copy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastmean_mcp import analysis
from fastmean_mcp.engine import EngineError


def document(*objects):
    return {"scm":{"Scheme":{"Objects":list(objects)}}}


def component(name="C1"):
    return {"Name":name,"Type":1001,"Params":{"C":1e-6,"IC":0.}}


def instance(name, path):
    return {"Name":name,"Type":7100,"Params":{"FileName":str(path)}}


class AnalysisHierarchyBoundsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fm-analysis-bounds-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.private = self.root/"circuit.scm"

    def graph(self, levels, branching=1):
        paths = [self.private]+[self.root/f"model_{index}.scm" for index in range(1,levels)]
        documents = {paths[-1]:document(component())}
        for index in range(levels-1):
            documents[paths[index]] = document(*(instance(f"X{branch}",paths[index+1]) for branch in range(branching)))
        return documents

    def cloning_fixture(self):
        child = self.root/"child.scm"
        documents = {self.private:document(instance("FIRST",child),instance("SECOND",child)),
                     child:document(component())}
        manifest = {"source_models":[{"source_path":str(path),"private_path":str(path)} for path in documents]}
        return documents,manifest,child

    def test_small_acyclic_dag_cannot_expand_exponentially_without_a_bound(self):
        documents = self.graph(20,branching=2)
        original = copy.deepcopy(documents)
        with patch.object(analysis,"MAX_EXPANDED_OBJECTS",50):
            found = []
            with self.assertRaisesRegex(EngineError,"50 expanded objects"):
                for item in analysis._active_components(self.private,documents):
                    found.append(item)
        self.assertEqual(len(found),50)
        self.assertEqual(documents,original)
        self.assertFalse(list(self.root.iterdir()))

    def test_expansion_observes_cancellation_before_visiting_another_object(self):
        documents = self.graph(5,branching=2)
        cancelled = threading.Event()
        iterator = analysis._active_components(self.private,documents,cancelled=cancelled)
        next(iterator)
        cancelled.set()
        with self.assertRaisesRegex(EngineError,"cancelled"):
            next(iterator)

    def test_analysis_depth_is_bounded_independently_of_python_recursion(self):
        with patch.object(analysis,"MAX_ANALYSIS_DEPTH",2):
            with self.assertRaisesRegex(EngineError,"2 instance levels"):
                list(analysis._active_components(self.private,self.graph(5)))

    def test_root_only_self_test_remains_finite_and_cycles_fail_clearly(self):
        documents = {self.private:document(instance("_SELF",self.private),component())}
        found = list(analysis._active_components(self.private,documents))
        self.assertEqual([item[2] for item in found],["_SELF","_SELF.C1","C1"])
        documents = {self.private:document(instance("A",self.private))}
        with self.assertRaisesRegex(EngineError,"cycle"):
            list(analysis._active_components(self.private,documents))

    def test_expansion_does_not_follow_an_unprepared_external_reference(self):
        documents = {self.private:document(instance("A",self.root.parent/"outside.scm"))}
        with self.assertRaisesRegex(EngineError,"escaped"):
            list(analysis._active_components(self.private,documents))

    def test_private_file_budget_is_checked_before_deepcopy_or_directory_creation(self):
        documents,manifest,_ = self.cloning_fixture()
        original = copy.deepcopy(documents)
        with patch.object(analysis,"MAX_MODEL_FILES",2),patch.object(analysis.copy,"deepcopy") as clone:
            with self.assertRaisesRegex(EngineError,"2 SCM model files"):
                analysis._component(self.private,"FIRST.C1",documents,manifest)
            clone.assert_not_called()
        self.assertEqual(documents,original)
        self.assertFalse(list(self.root.iterdir()))

    def test_private_byte_budget_is_checked_before_deepcopy_or_writes(self):
        documents,manifest,_ = self.cloning_fixture()
        with patch.object(analysis,"MAX_PROJECT_BYTES",100),patch.object(analysis.copy,"deepcopy") as clone:
            with self.assertRaisesRegex(EngineError,"100 bytes"):
                analysis._component(self.private,"FIRST.C1",documents,manifest)
            clone.assert_not_called()
        self.assertFalse(list(self.root.iterdir()))

    def test_clone_bytes_cannot_push_an_initially_valid_project_over_the_limit(self):
        documents,manifest,child = self.cloning_fixture()
        original_size = sum(analysis._document_byte_estimate(value) for value in documents.values())
        candidate_size = analysis._document_byte_estimate(documents[child])
        limit = original_size + candidate_size//2
        with patch.object(analysis,"MAX_PROJECT_BYTES",limit),patch.object(analysis.copy,"deepcopy") as clone:
            with self.assertRaisesRegex(EngineError,"after instance cloning"):
                analysis._component(self.private,"FIRST.C1",documents,manifest)
            clone.assert_not_called()
        self.assertFalse(list(self.root.iterdir()))

    def test_pending_in_memory_clones_count_toward_the_file_limit(self):
        documents,manifest,child = self.cloning_fixture()
        with patch.object(analysis,"MAX_MODEL_FILES",3):
            _,target = analysis._component(self.private,"FIRST.C1",documents,manifest)
            target["Params"]["IC"] = .7
            with self.assertRaisesRegex(EngineError,"3 SCM model files"):
                analysis._component(self.private,"SECOND.C1",documents,manifest)
        self.assertEqual(documents[child]["scm"]["Scheme"]["Objects"][0]["Params"]["IC"],0.)
        self.assertEqual(len(manifest["source_models"]),3)
        self.assertTrue(manifest["instance_model_clones"][0]["private_byte_estimate"] > 0)
        self.assertFalse(list(self.root.rglob("*.scm")))

    def test_clone_preparation_observes_preexisting_cancellation(self):
        documents,manifest,_ = self.cloning_fixture()
        cancelled = threading.Event()
        cancelled.set()
        with patch.object(analysis.copy,"deepcopy") as clone:
            with self.assertRaisesRegex(EngineError,"cancelled"):
                analysis._component(self.private,"FIRST.C1",documents,manifest,cancelled=cancelled)
            clone.assert_not_called()
        self.assertFalse(list(self.root.iterdir()))


if __name__ == "__main__":
    unittest.main()
