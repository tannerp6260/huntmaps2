"""Regression for accidentally downloading historical tile revisions."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from glassing.acquire import acquire


class AcquisitionTests(unittest.TestCase):
    def test_pinned_revision_only_is_requested(self):
        c=json.loads(Path('configs/gmu54.json').read_text())
        fixture=Path('docs/glassing/provenance')
        requested=[]
        with tempfile.TemporaryDirectory() as directory:
            c['inputs']=directory
            class FakeFetcher:
                def __init__(self,root,budget):self.used=0;self.budget=budget
                def json(self,name,url,**kw):
                    value=json.loads((fixture/name).read_text())
                    Path(directory,name).write_text((fixture/name).read_text())
                    return value
                def get(self,name,url,**kw):
                    requested.append(name)
                    return fixture/'dem_info.json'
            with patch('glassing.acquire.Fetcher',FakeFetcher),patch('glassing.acquire.digest',side_effect=lambda p:c['boundary_sha256'] if Path(p).name=='gmu54.geojson' else c['dem_sha256']):
                acquire(c)
        self.assertEqual(requested,[c['dem_product']])

if __name__=='__main__':unittest.main()
