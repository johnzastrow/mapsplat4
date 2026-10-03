"""
MapSplat - layer order tests (issue #4)

sort_layers_by_tree_order() must reproduce the QGIS layer-tree order in the style for both
PMTiles modes. In single-file mode every vector layer shares the one 'mapsplat' source and is
identified only by its source-layer; online XYZ base layers are 'tile_<name>' sources.
"""

__version__ = "0.1.0"

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exporter import sort_layers_by_tree_order  # noqa: E402

# QGIS panel order, top first: an ungrouped point layer above a group, the group's members,
# an ungrouped layer below the group, then two online XYZ base layers at the bottom.
TREE = ["Notable_features", "Possible_infrastructure", "Possible_canal",
        "Mapping_extent", "Google_Aerial", "OSM_Standard"]


def _ids(layers):
    return [ly["id"] for ly in layers]


def _single_file_layers():
    """Style layers as single-file mode emits them, in a scrambled pre-sort order."""
    return [
        {"id": "Possible_canal", "type": "line", "source": "mapsplat",
         "source-layer": "Possible_canal"},
        {"id": "Mapping_extent", "type": "fill", "source": "mapsplat",
         "source-layer": "Mapping_extent"},
        {"id": "Notable_features", "type": "symbol", "source": "mapsplat",
         "source-layer": "Notable_features"},
        {"id": "Notable_features_labels", "type": "symbol", "source": "mapsplat",
         "source-layer": "Notable_features"},
        {"id": "Possible_infrastructure", "type": "fill", "source": "mapsplat",
         "source-layer": "Possible_infrastructure"},
        {"id": "tile_Google_Aerial_raster", "type": "raster", "source": "tile_Google_Aerial"},
        {"id": "tile_OSM_Standard_raster", "type": "raster", "source": "tile_OSM_Standard"},
    ]


# Expected draw order (bottom first): base layers at the bottom, the top tree layer last.
EXPECTED = ["tile_OSM_Standard_raster", "tile_Google_Aerial_raster", "Mapping_extent",
            "Possible_canal", "Possible_infrastructure",
            "Notable_features", "Notable_features_labels"]


class TestSingleFileMode(unittest.TestCase):
    def test_matches_tree_order(self):
        self.assertEqual(_ids(sort_layers_by_tree_order(_single_file_layers(), TREE)), EXPECTED)

    def test_online_base_layers_drawn_below_all_data(self):
        out = _ids(sort_layers_by_tree_order(_single_file_layers(), TREE))
        self.assertEqual(out[:2], ["tile_OSM_Standard_raster", "tile_Google_Aerial_raster"])

    def test_ungrouped_layer_above_a_group_stays_above_it(self):
        out = _ids(sort_layers_by_tree_order(_single_file_layers(), TREE))
        self.assertGreater(out.index("Notable_features"), out.index("Possible_infrastructure"))

    def test_result_independent_of_input_order(self):
        layers = _single_file_layers()
        self.assertEqual(_ids(sort_layers_by_tree_order(list(reversed(layers)), TREE))[:5],
                         EXPECTED[:5])


class TestPerLayerMode(unittest.TestCase):
    def test_matches_tree_order(self):
        layers = [dict(ly) for ly in _single_file_layers()]
        for ly in layers:  # per-layer mode: each vector layer has a source named after it
            if ly["source"] == "mapsplat":
                ly["source"] = ly["source-layer"]
        self.assertEqual(_ids(sort_layers_by_tree_order(layers, TREE)), EXPECTED)


class TestRules(unittest.TestCase):
    def test_style_layers_of_one_qgis_layer_keep_their_order(self):
        layers = [
            {"id": "paths_rule0", "source": "mapsplat", "source-layer": "paths"},
            {"id": "roads", "source": "mapsplat", "source-layer": "roads"},
            {"id": "paths_rule1_2", "source": "mapsplat", "source-layer": "paths"},
            {"id": "paths_labels", "source": "mapsplat", "source-layer": "paths"},
        ]
        out = _ids(sort_layers_by_tree_order(layers, ["paths", "roads"]))
        self.assertEqual(out, ["roads", "paths_rule0", "paths_rule1_2", "paths_labels"])

    def test_layer_missing_from_tree_sinks_to_bottom(self):
        layers = [
            {"id": "a", "source": "mapsplat", "source-layer": "a"},
            {"id": "ghost", "source": "mapsplat", "source-layer": "ghost"},
        ]
        self.assertEqual(_ids(sort_layers_by_tree_order(layers, ["a"])), ["ghost", "a"])

    def test_vector_tile_layer_ranked_by_its_source_not_its_source_layer(self):
        # A styled vector-tile service ('tile_Carto') whose internal source-layer 'water'
        # shares a name with one of the user's own layers must follow the tile layer's
        # position in the tree, not the user's 'water' layer.
        layers = [
            {"id": "carto_water", "source": "tile_Carto", "source-layer": "water"},
            {"id": "water", "source": "mapsplat", "source-layer": "water"},
        ]
        out = _ids(sort_layers_by_tree_order(layers, ["water", "Carto"]))
        self.assertEqual(out, ["carto_water", "water"])


if __name__ == "__main__":
    unittest.main()
