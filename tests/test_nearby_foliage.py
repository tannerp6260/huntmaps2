import unittest
from unittest.mock import patch
import numpy as np
from huntmaps_gui import vegetation_screen as v

class NearbyFoliage(unittest.TestCase):
    def test_range_boundary_and_cap(self):
        c=np.array([[30,0,0],[30.001,0,0],[0,0,-60]],dtype=float)
        np.testing.assert_array_equal(v.nearby(c,30),[0]);np.testing.assert_array_equal(v.nearby(c,60),[0,1,2])
        for r in [0,29,300,True,'30']:
            with self.assertRaises(ValueError):v.nearby(c,r)
        with patch.object(v,'DISPLAY_CAP',1):
            with self.assertRaisesRegex(ValueError,'No clumps were silently discarded'):v.nearby(c,60)
    def test_shared_primitive(self):
        shape=v.primitive();vertices=np.array(shape['vertices']);faces=np.array(shape['faces'])
        self.assertEqual(vertices.shape,(12,3));self.assertEqual(faces.shape,(20,3))
        np.testing.assert_allclose(np.linalg.norm(vertices,axis=1),1,atol=1e-7)
        for f in faces:
            a,b,c=vertices[f];self.assertGreater(np.dot(np.cross(b-a,c-a),a),0)
    def test_independent_triangle_intersections(self):
        shape=v.primitive();verts=np.array(shape['vertices'],float)*.75;faces=np.array(shape['faces'])
        rng=np.random.default_rng(30)
        for _ in range(120):
            start=rng.normal(size=3)*2;end=rng.normal(size=3)*2;direction=end-start;hits=[]
            for face in faces:
                a,b,c=verts[face];e1=b-a;e2=c-a;h=np.cross(direction,e2);det=np.dot(e1,h)
                if abs(det)<1e-12:continue
                inv=1/det;s=start-a;u=inv*np.dot(s,h);q=np.cross(s,e1);w=inv*np.dot(direction,q);t=inv*np.dot(e2,q)
                if u>=-1e-9 and w>=-1e-9 and u+w<=1+1e-9 and 0<=t<=1:hits.append(t)
            # Starts outside the unit sphere must be outside the convex primitive.
            if np.linalg.norm(start)<=.75:continue
            actual=v.poly_intersect(np.zeros((1,3)),start,end,1.5,shape)[0]
            if hits:self.assertAlmostEqual(actual,min(hits))
            else:self.assertIsNone(actual)
    def test_inside_parallel_and_monotonicity(self):
        shape=v.primitive();c=np.array([[0,0,0],[5,0,0]],dtype=np.float32)
        hit=v.poly_intersect(c,[0,0,0],[5,0,0],1,shape)
        self.assertEqual(hit[0],0);self.assertTrue(hit[2]);self.assertTrue(hit[3])
        self.assertIsNone(v.poly_intersect(c,[0,2,0],[10,2,0],1,shape)[0])
        r=v.evaluate(c,[-3,.5,0],[10,.5,0],13,0,'medium',shape=shape,radius=30)
        counts=[r['scenarios'][name]['intersected_cells'] for name in v.SCENARIOS]
        self.assertEqual(counts,sorted(counts));self.assertEqual(r['geometry_identifier'],v.GEOMETRY)
    def test_far_screen_is_unevaluated(self):
        c=np.array([[60,1,0]],dtype=np.float32)
        r=v.evaluate(c,[0,1,0],[100,1,0],100,0,'medium',shape=v.primitive(),radius=30)
        self.assertEqual(r['included_cell_count'],0);self.assertTrue(r['farther_vegetation_unevaluated'])
        self.assertEqual(r['scenarios']['medium']['result'],'no modeled intersection')
        r=v.evaluate(c,[0,1,0],[100,1,0],100,0,'medium',shape=v.primitive(),radius=60)
        self.assertIsNotNone(r['scenarios']['medium']['first_intersection'])
    def test_color_alignment_alpha_median_and_determinism(self):
        rgba=np.zeros((9,9,4),dtype=np.uint8)
        rgba[:4,:4]=[100,150,200,255];rgba[5:,5:]=[200,80,40,255]
        # radius4.5 gives1m pixels. north-positive maps to top rows.
        c=np.array([[-3,0,-3],[3,0,3],[8,0,8]],dtype=np.float32);k=np.ones(3,dtype=np.uint8)
        colors,used=v.foliage_colors(c,k,rgba,4.5)
        np.testing.assert_array_equal(used,[True,True,False])
        np.testing.assert_array_equal(colors[0],np.rint(.75*np.array([100,150,200])+.25*np.array([72,108,53])))
        np.testing.assert_array_equal(colors[1],np.rint(.75*np.array([200,80,40])+.25*np.array([72,108,53])))
        np.testing.assert_array_equal(colors[2],[72,108,53])
        np.testing.assert_array_equal(colors,v.foliage_colors(c,k,rgba,4.5)[0])
