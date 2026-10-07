"""
generate_test_fixtures.py
=========================
Generates the 13 minimal deterministic .bubridge test fixtures required for
Milestone 4 Unreal package reader validation.
"""

import json
from pathlib import Path
import shutil

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "test_assets" / "fixtures"

FIXED_TIMESTAMP = "2026-10-05T12:00:00Z"

BASE_MANIFEST = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "format": "BUBRIDGE",
    "version": "0.1.0",
    "created_at": FIXED_TIMESTAMP,
    "generator": {
        "name": "BlenderUnrealBridgeAddon",
        "version": "0.1.0"
    },
    "source": {
        "application": "Blender",
        "version": "4.5.3 LTS",
        "scene_name": "FixtureScene",
        "unit_length": "meter",
        "unit_scale": 1.0
    },
    "target": {
        "application": "Unreal Engine",
        "version": "5.x",
        "unit_length": "centimeter"
    },
    "coordinate_system": {
        "up_axis": "Z",
        "forward_axis": "X",
        "right_axis": "Y",
        "handedness": "left_handed",
        "unit": "centimeter"
    },
    "content_summary": {
        "object_count": 1,
        "mesh_count": 0,
        "material_count": 0,
        "texture_count": 0
    }
}

BASE_SCENE = {
    "name": "FixtureScene",
    "collections": [],
    "environment": {
        "background_color": [0.05, 0.05, 0.05, 1.0],
        "ambient_intensity": 1.0
    }
}

IDENTITY_XFORM = {
    "location": [0.0, 0.0, 0.0],
    "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
    "rotation_euler": [0.0, 0.0, 0.0],
    "rotation_mode": "QUATERNION",
    "scale": [1.0, 1.0, 1.0],
    "has_negative_scale": False,
    "origin_offset": [0.0, 0.0, 0.0]
}


def write_fixture(name: str, manifest: dict, scene: dict, objects: list, meshes: dict = None, materials: dict = None):
    pkg_dir = FIXTURES_DIR / f"{name}.bubridge"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "meshes").mkdir(exist_ok=True)
    (pkg_dir / "materials").mkdir(exist_ok=True)
    (pkg_dir / "textures").mkdir(exist_ok=True)
    (pkg_dir / "metadata").mkdir(exist_ok=True)

    manifest_copy = dict(manifest)
    manifest_copy["content_summary"] = dict(manifest_copy.get("content_summary", {}))
    manifest_copy["content_summary"]["object_count"] = len(objects)
    manifest_copy["content_summary"]["mesh_count"] = len(meshes) if meshes else 0
    manifest_copy["content_summary"]["material_count"] = len(materials) if materials else 0

    (pkg_dir / "manifest.json").write_text(json.dumps(manifest_copy, indent=2), encoding="utf-8")
    (pkg_dir / "scene.json").write_text(json.dumps(scene, indent=2), encoding="utf-8")
    (pkg_dir / "objects.json").write_text(json.dumps({"objects": objects}, indent=2), encoding="utf-8")

    if meshes:
        for mesh_id, mesh_data in meshes.items():
            (pkg_dir / "meshes" / f"{mesh_id}.json").write_text(json.dumps(mesh_data, indent=2), encoding="utf-8")

    if materials:
        for mat_id, mat_data in materials.items():
            (pkg_dir / "materials" / f"{mat_id}.json").write_text(json.dumps(mat_data, indent=2), encoding="utf-8")

    report = {
        "timestamp": FIXED_TIMESTAMP,
        "status": "SUCCESS",
        "summary": {"info_count": 0, "warning_count": 0, "error_count": 0},
        "messages": []
    }
    (pkg_dir / "metadata" / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def generate_all_fixtures():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Identity scene
    write_fixture(
        "01_identity_scene",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000001",
            "name": "IdentityObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": None,
            "material_slots": []
        }]
    )

    # 2. Single translated object
    tx_xform = dict(IDENTITY_XFORM)
    tx_xform["location"] = [250.0, -100.0, 50.0]
    write_fixture(
        "02_single_translated",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000002",
            "name": "TranslatedObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": tx_xform,
            "mesh_reference": None,
            "material_slots": []
        }]
    )

    # 3. Rotated object (90 deg around Z)
    rot_xform = dict(IDENTITY_XFORM)
    rot_xform["rotation_quaternion"] = [0.0, 0.0, 0.7071068, 0.7071068]
    rot_xform["rotation_euler"] = [0.0, 0.0, 90.0]
    write_fixture(
        "03_rotated_object",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000003",
            "name": "RotatedObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": rot_xform,
            "mesh_reference": None,
            "material_slots": []
        }]
    )

    # 4. Scaled object (non-uniform)
    sc_xform = dict(IDENTITY_XFORM)
    sc_xform["scale"] = [2.0, 0.5, 3.0]
    write_fixture(
        "04_scaled_object",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000004",
            "name": "ScaledObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": sc_xform,
            "mesh_reference": None,
            "material_slots": []
        }]
    )

    # 5. Negative scale object
    neg_xform = dict(IDENTITY_XFORM)
    neg_xform["scale"] = [-1.0, 1.0, 1.0]
    neg_xform["has_negative_scale"] = True
    write_fixture(
        "05_negative_scale",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000005",
            "name": "NegativeScaleObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": neg_xform,
            "mesh_reference": None,
            "material_slots": []
        }]
    )

    # 6. Parent-child hierarchy
    p_xform = dict(IDENTITY_XFORM)
    p_xform["location"] = [100.0, 0.0, 0.0]
    c_xform = dict(IDENTITY_XFORM)
    c_xform["location"] = [0.0, 50.0, 0.0]
    write_fixture(
        "06_parent_child",
        BASE_MANIFEST,
        BASE_SCENE,
        [
            {
                "id": "obj_00000006",
                "name": "ParentObj",
                "type": "EMPTY",
                "visible": True,
                "collection_id": None,
                "parent_id": None,
                "transform": p_xform,
                "mesh_reference": None,
                "material_slots": []
            },
            {
                "id": "obj_00000007",
                "name": "ChildObj",
                "type": "STATIC_MESH",
                "visible": True,
                "collection_id": None,
                "parent_id": "obj_00000006",
                "transform": c_xform,
                "mesh_reference": None,
                "material_slots": []
            }
        ]
    )

    # 7. Deep hierarchy (Grandparent -> Parent -> Child)
    gp_xform = dict(IDENTITY_XFORM)
    gp_xform["location"] = [0.0, 0.0, 100.0]
    write_fixture(
        "07_deep_hierarchy",
        BASE_MANIFEST,
        BASE_SCENE,
        [
            {
                "id": "obj_00000008",
                "name": "Grandparent",
                "type": "EMPTY",
                "visible": True,
                "collection_id": None,
                "parent_id": None,
                "transform": gp_xform,
                "mesh_reference": None,
                "material_slots": []
            },
            {
                "id": "obj_00000009",
                "name": "Parent",
                "type": "EMPTY",
                "visible": True,
                "collection_id": None,
                "parent_id": "obj_00000008",
                "transform": p_xform,
                "mesh_reference": None,
                "material_slots": []
            },
            {
                "id": "obj_0000000a",
                "name": "Child",
                "type": "STATIC_MESH",
                "visible": True,
                "collection_id": None,
                "parent_id": "obj_00000009",
                "transform": c_xform,
                "mesh_reference": None,
                "material_slots": []
            }
        ]
    )

    # 8. Invalid manifest (wrong format identifier)
    inv_manifest = dict(BASE_MANIFEST)
    inv_manifest["format"] = "INVALID_FORMAT"
    write_fixture(
        "08_invalid_manifest",
        inv_manifest,
        BASE_SCENE,
        [{
            "id": "obj_0000000b",
            "name": "Obj",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": None,
            "material_slots": []
        }]
    )

    # 9. Duplicate ID
    write_fixture(
        "09_duplicate_id",
        BASE_MANIFEST,
        BASE_SCENE,
        [
            {
                "id": "obj_0000000c",
                "name": "ObjA",
                "type": "STATIC_MESH",
                "visible": True,
                "collection_id": None,
                "parent_id": None,
                "transform": IDENTITY_XFORM,
                "mesh_reference": None,
                "material_slots": []
            },
            {
                "id": "obj_0000000c",  # Duplicate
                "name": "ObjB",
                "type": "STATIC_MESH",
                "visible": True,
                "collection_id": None,
                "parent_id": None,
                "transform": IDENTITY_XFORM,
                "mesh_reference": None,
                "material_slots": []
            }
        ]
    )

    # 10. Broken parent reference
    write_fixture(
        "10_broken_parent",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_0000000d",
            "name": "OrphanObj",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": "obj_nonexistent_parent",
            "transform": IDENTITY_XFORM,
            "mesh_reference": None,
            "material_slots": []
        }]
    )

    # 11. Hierarchy cycle (A -> B -> A)
    write_fixture(
        "11_hierarchy_cycle",
        BASE_MANIFEST,
        BASE_SCENE,
        [
            {
                "id": "obj_0000000e",
                "name": "CycleNodeA",
                "type": "EMPTY",
                "visible": True,
                "collection_id": None,
                "parent_id": "obj_0000000f",
                "transform": IDENTITY_XFORM,
                "mesh_reference": None,
                "material_slots": []
            },
            {
                "id": "obj_0000000f",
                "name": "CycleNodeB",
                "type": "EMPTY",
                "visible": True,
                "collection_id": None,
                "parent_id": "obj_0000000e",
                "transform": IDENTITY_XFORM,
                "mesh_reference": None,
                "material_slots": []
            }
        ]
    )

    # 12. Invalid transform (non-finite / missing numbers)
    bad_xform = dict(IDENTITY_XFORM)
    bad_xform["location"] = ["invalid_str", 0.0, 0.0]
    write_fixture(
        "12_invalid_transform",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000010",
            "name": "BadXformObj",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": bad_xform,
            "mesh_reference": None,
            "material_slots": []
        }]
    )

    # 13. Unsupported protocol version (Major 9)
    unsupp_manifest = dict(BASE_MANIFEST)
    unsupp_manifest["version"] = "9.0.0"
    write_fixture(
        "13_unsupported_version",
        unsupp_manifest,
        BASE_SCENE,
        [{
            "id": "obj_00000011",
            "name": "FutureVersionObj",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": None,
            "material_slots": []
        }]
    )

    # 14. Valid Mesh Payload
    valid_mesh = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "format": "BUBRIDGE_MESH",
        "version": "0.1.0",
        "mesh_id": "mesh_00000001",
        "name": "TestCubeMesh",
        "source": {
            "application": "Blender",
            "version": "4.5.3 LTS"
        },
        "coordinate_system": {
            "up_axis": "Z",
            "forward_axis": "X",
            "right_axis": "Y",
            "handedness": "left_handed",
            "unit": "centimeter"
        },
        "counts": {
            "vertex_count": 4,
            "triangle_count": 2,
            "uv_layer_count": 1,
            "material_slot_count": 1
        },
        "bounds": {
            "min": [-50.0, -50.0, 0.0],
            "max": [50.0, 50.0, 100.0]
        },
        "vertices": [
            [-50.0, -50.0, 0.0],
            [50.0, -50.0, 0.0],
            [50.0, 50.0, 0.0],
            [-50.0, 50.0, 0.0]
        ],
        "triangles": [
            {
                "vertex_indices": [0, 2, 1],
                "normals": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
                "uvs": [[0.0, 0.0], [1.0, 1.0], [1.0, 0.0]],
                "material_slot_index": 0
            },
            {
                "vertex_indices": [0, 3, 2],
                "normals": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
                "uvs": [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
                "material_slot_index": 0
            }
        ],
        "material_slots": [
            {
                "slot_index": 0,
                "slot_name": "M_Default",
                "material_id": None
            }
        ]
    }

    write_fixture(
        "14_mesh_payload",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000012",
            "name": "MeshObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": {
                "mesh_id": "mesh_00000001",
                "file": "meshes/mesh_00000001.json",
                "submesh_index": 0
            },
            "material_slots": [
                {
                    "slot_index": 0,
                    "slot_name": "M_Default",
                    "material_id": None
                }
            ]
        }],
        meshes={"mesh_00000001": valid_mesh}
    )

    # 15. Broken Mesh Reference
    write_fixture(
        "15_broken_mesh_ref",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000013",
            "name": "BrokenMeshObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": {
                "mesh_id": "mesh_99999999",
                "file": "meshes/mesh_99999999.json",
                "submesh_index": 0
            },
            "material_slots": []
        }],
        meshes={}
    )

    # 16. Out-of-bounds Triangle Index
    bad_index_mesh = dict(valid_mesh)
    bad_index_mesh["mesh_id"] = "mesh_00000002"
    bad_index_mesh["triangles"] = [
        {
            "vertex_indices": [0, 999, 1],  # Index 999 out of bounds (vertex count: 4)
            "normals": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
            "uvs": [[0.0, 0.0], [1.0, 1.0], [1.0, 0.0]],
            "material_slot_index": 0
        }
    ]

    write_fixture(
        "16_mesh_index_out_of_bounds",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000014",
            "name": "BadMeshObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": {
                "mesh_id": "mesh_00000002",
                "file": "meshes/mesh_00000002.json",
                "submesh_index": 0
            },
            "material_slots": []
        }],
        meshes={"mesh_00000002": bad_index_mesh}
    )

    # 17. Valid Material Payload
    mat_pbr_red = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "format": "BUBRIDGE_MATERIAL",
        "version": "0.1.0",
        "material_id": "mat_00000001",
        "name": "M_RedRough",
        "model": "PBR_METALLIC_ROUGHNESS",
        "properties": {
            "base_color": [0.8, 0.1, 0.1, 1.0],
            "metallic": 0.0,
            "roughness": 0.8,
            "specular": 0.5,
            "ior": 1.5,
            "opacity": 1.0,
            "blend_mode": "OPAQUE",
            "two_sided": False
        }
    }

    mesh_with_mat = dict(valid_mesh)
    mesh_with_mat["mesh_id"] = "mesh_00000003"
    mesh_with_mat["material_slots"] = [
        {
            "slot_index": 0,
            "slot_name": "M_RedRough",
            "material_id": "mat_00000001"
        }
    ]

    write_fixture(
        "17_material_payload",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000015",
            "name": "MaterialObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": {
                "mesh_id": "mesh_00000003",
                "file": "meshes/mesh_00000003.json",
                "submesh_index": 0
            },
            "material_slots": [
                {
                    "slot_index": 0,
                    "slot_name": "M_RedRough",
                    "material_id": "mat_00000001"
                }
            ]
        }],
        meshes={"mesh_00000003": mesh_with_mat},
        materials={"mat_00000001": mat_pbr_red}
    )

    # 18. Multi-Material Payload
    mat_pbr_blue = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "format": "BUBRIDGE_MATERIAL",
        "version": "0.1.0",
        "material_id": "mat_00000002",
        "name": "M_BlueMetal",
        "model": "PBR_METALLIC_ROUGHNESS",
        "properties": {
            "base_color": [0.1, 0.2, 0.9, 1.0],
            "metallic": 1.0,
            "roughness": 0.2,
            "specular": 0.5,
            "ior": 1.5,
            "opacity": 1.0,
            "blend_mode": "OPAQUE",
            "two_sided": True
        }
    }

    multi_mat_mesh = dict(valid_mesh)
    multi_mat_mesh["mesh_id"] = "mesh_00000004"
    multi_mat_mesh["material_slots"] = [
        {
            "slot_index": 0,
            "slot_name": "M_RedRough",
            "material_id": "mat_00000001"
        },
        {
            "slot_index": 1,
            "slot_name": "M_BlueMetal",
            "material_id": "mat_00000002"
        }
    ]
    multi_mat_mesh["triangles"] = [
        {
            "vertex_indices": [0, 2, 1],
            "normals": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
            "uvs": [[0.0, 0.0], [1.0, 1.0], [1.0, 0.0]],
            "material_slot_index": 0
        },
        {
            "vertex_indices": [0, 3, 2],
            "normals": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
            "uvs": [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
            "material_slot_index": 1
        }
    ]

    write_fixture(
        "18_multi_material_payload",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000016",
            "name": "MultiMatObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": {
                "mesh_id": "mesh_00000004",
                "file": "meshes/mesh_00000004.json",
                "submesh_index": 0
            },
            "material_slots": [
                {
                    "slot_index": 0,
                    "slot_name": "M_RedRough",
                    "material_id": "mat_00000001"
                },
                {
                    "slot_index": 1,
                    "slot_name": "M_BlueMetal",
                    "material_id": "mat_00000002"
                }
            ]
        }],
        meshes={"mesh_00000004": multi_mat_mesh},
        materials={
            "mat_00000001": mat_pbr_red,
            "mat_00000002": mat_pbr_blue
        }
    )

    # 19. Broken Material Reference
    broken_mat_mesh = dict(valid_mesh)
    broken_mat_mesh["mesh_id"] = "mesh_00000005"
    broken_mat_mesh["material_slots"] = [
        {
            "slot_index": 0,
            "slot_name": "M_Missing",
            "material_id": "mat_99999999"
        }
    ]

    write_fixture(
        "19_broken_material_ref",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000017",
            "name": "BrokenMatObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": {
                "mesh_id": "mesh_00000005",
                "file": "meshes/mesh_00000005.json",
                "submesh_index": 0
            },
            "material_slots": [
                {
                    "slot_index": 0,
                    "slot_name": "M_Missing",
                    "material_id": "mat_99999999"
                }
            ]
        }],
        meshes={"mesh_00000005": broken_mat_mesh},
        materials={}
    )

    # 20. Invalid PBR Value (Metallic out of range 2.5)
    invalid_pbr_mat = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "format": "BUBRIDGE_MATERIAL",
        "version": "0.1.0",
        "material_id": "mat_00000003",
        "name": "M_BadMetallic",
        "model": "PBR_METALLIC_ROUGHNESS",
        "properties": {
            "base_color": [0.8, 0.8, 0.8, 1.0],
            "metallic": 2.5,
            "roughness": 0.5,
            "specular": 0.5,
            "ior": 1.5,
            "opacity": 1.0,
            "blend_mode": "OPAQUE",
            "two_sided": False
        }
    }

    bad_mat_mesh = dict(valid_mesh)
    bad_mat_mesh["mesh_id"] = "mesh_00000006"
    bad_mat_mesh["material_slots"] = [
        {
            "slot_index": 0,
            "slot_name": "M_BadMetallic",
            "material_id": "mat_00000003"
        }
    ]

    write_fixture(
        "20_invalid_pbr_value",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000018",
            "name": "InvalidPbrObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": {
                "mesh_id": "mesh_00000006",
                "file": "meshes/mesh_00000006.json",
                "submesh_index": 0
            },
            "material_slots": [
                {
                    "slot_index": 0,
                    "slot_name": "M_BadMetallic",
                    "material_id": "mat_00000003"
                }
            ]
        }],
        meshes={"mesh_00000006": bad_mat_mesh},
        materials={"mat_00000003": invalid_pbr_mat}
    )

    # 21. Invalid Material Schema
    invalid_schema_mat = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "format": "BUBRIDGE_BAD_FORMAT",
        "version": "0.1.0",
        "material_id": "invalid_id_not_mat",
        "name": "M_BadSchema",
        "model": "UNKNOWN_MODEL",
        "properties": {
            "base_color": [0.8, 0.8, 0.8, 1.0]
        }
    }

    bad_schema_mesh = dict(valid_mesh)
    bad_schema_mesh["mesh_id"] = "mesh_00000007"
    bad_schema_mesh["material_slots"] = [
        {
            "slot_index": 0,
            "slot_name": "M_BadSchema",
            "material_id": "invalid_id_not_mat"
        }
    ]

    write_fixture(
        "21_invalid_material_schema",
        BASE_MANIFEST,
        BASE_SCENE,
        [{
            "id": "obj_00000019",
            "name": "InvalidSchemaObject",
            "type": "STATIC_MESH",
            "visible": True,
            "collection_id": None,
            "parent_id": None,
            "transform": IDENTITY_XFORM,
            "mesh_reference": {
                "mesh_id": "mesh_00000007",
                "file": "meshes/mesh_00000007.json",
                "submesh_index": 0
            },
            "material_slots": [
                {
                    "slot_index": 0,
                    "slot_name": "M_BadSchema",
                    "material_id": "invalid_id_not_mat"
                }
            ]
        }],
        meshes={"mesh_00000007": bad_schema_mesh},
        materials={"invalid_id_not_mat": invalid_schema_mat}
    )

    print(f"Generated 21 test fixtures in {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_all_fixtures()
