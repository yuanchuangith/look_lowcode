from __future__ import annotations

import random
import unittest

from gxp_core.business_graph_algorithms import components


class BusinessGraphAlgorithmsTests(unittest.TestCase):
    def test_components_match_disjoint_set_reference(self):
        randomizer = random.Random(20260930)
        for trial in range(300):
            with self.subTest(trial=trial):
                nodes = [{"id": f"node-{index}"} for index in range(randomizer.randrange(60))]
                randomizer.shuffle(nodes)
                identifiers = [node["id"] for node in nodes] + ["outside-scope"]
                edges = [{"id": f"edge-{index}", "source": randomizer.choice(identifiers),
                          "target": randomizer.choice(identifiers)} for index in range(randomizer.randrange(180))]
                parents = {node["id"]: node["id"] for node in nodes}

                def representative(identifier):
                    while parents[identifier] != identifier:
                        identifier = parents[identifier]
                    return identifier

                for edge in edges:
                    if edge["source"] in parents and edge["target"] in parents:
                        parents[representative(edge["source"])] = representative(edge["target"])
                groups = {}
                for identifier in parents:
                    groups.setdefault(representative(identifier), []).append(identifier)
                expected = sorted(sorted(group) for group in groups.values())
                self.assertEqual(components(nodes, edges), expected)

    def test_large_fragmented_graph_keeps_all_components_ordered(self):
        nodes = [{"id": f"node-{index:05d}"} for index in reversed(range(10000))]
        edges = [{"id": f"edge-{index}", "source": f"node-{index:05d}", "target": f"node-{index + 1:05d}"}
                 for index in range(0, 5000, 2)]
        expected = [[f"node-{index:05d}", f"node-{index + 1:05d}"] for index in range(0, 5000, 2)]
        expected.extend([f"node-{index:05d}"] for index in range(5000, 10000))
        self.assertEqual(components(nodes, edges), expected)


if __name__ == "__main__":
    unittest.main()
