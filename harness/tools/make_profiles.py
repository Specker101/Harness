"""Erzeugt die Werkzeugprofile aus dem Ghidra-Werkzeugkatalog.

Quelle: g:\\Harness\\sandbox\\_ghidra_schema.json (Katalog des Plugins, 215 Werkzeuge;
erzeugt aus GET http://127.0.0.1:8089/mcp/schema). Die Allow-Listen sind
HANDGEPRUEFT (E4) - sie stehen unten wortgetreu als Konstanten und werden nur
gegen den Katalog geprueft (fehlende Namen werden gemeldet, nie stillschweigend
ergaenzt).

Aufruf:  python g:\\Harness\\harness\\tools\\make_profiles.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCHEMA = Path("g:/Harness/sandbox/_ghidra_schema.json")
OUT_DIR = ROOT / "profiles"

# ---------------------------------------------------------------- Handgeprueft

# Immer gesperrt (auch in "full").
NEVER_ALLOW = ["run_ghidra_script", "run_script_inline"]

# Hart gesperrt in ALLEN Profilen: Programm-/Projektzustand, DB-Schreiber,
# Verwalter, Nachladen von Werkzeugen. (GET != lesend!)
HARD_DENY = [
    # Programm-/Projektzustand (Harness-Sache, E7)
    "open_program", "switch_program", "load_program", "load_program_from_project",
    "close_program", "open_project", "close_project", "create_project",
    "restore_project", "archive_project", "checkin_program", "import_program",
    "import_file", "export_program", "delete_file", "create_folder",
    "save_program", "save_all_programs", "create_memory_block", "set_image_base",
    "reanalyze", "run_analysis", "set_program_option", "remove_program_option",
    # Property-Maps (Projektzustand, nur Harness/Ankerwerkzeuge)
    "set_property", "create_property_map", "delete_property_map", "remove_property",
    # Bridge-Verwaltung (Worker darf die reduzierte Liste nicht selbst erweitern)
    "list_instances", "connect_instance", "list_tool_groups", "load_tool_group",
    "unload_tool_group", "check_tools", "search_tools",
    # "unklar" (POST, Schreibwirkung nicht belegt) - konservativ gesperrt
    "analyze_data_region", "analyze_struct_field_usage", "batch_analyze_completeness",
    "detect_array_bounds", "emulate_function", "emulate_hash_batch",
    "get_assembly_context", "get_bulk_xrefs", "get_field_access_context",
    "suggest_field_names",
]

# Nur-Lese-Kernliste (HTTP GET, ohne die GETs mit Zustandswirkung:
# open_program / switch_program / save_program / save_all_programs).
READ_ALLOW = [
    # Programm-/Projektueberblick
    "get_metadata", "get_current_program_info", "list_open_programs", "get_address_spaces",
    "get_project_info", "get_language_metadata", "list_segments", "analysis_status",
    "list_analyzers", "list_scripts", "get_program_options", "list_option_groups",
    # Funktionen
    "list_functions", "list_functions_enhanced", "search_functions", "search_functions_enhanced",
    "search_functions_by_tag", "get_function_by_address", "get_function_count",
    "decompile_function", "batch_decompile", "force_decompile", "disassemble_function",
    "get_function_variables", "get_function_signature", "get_function_pcode",
    "get_function_tags", "list_function_tags", "get_function_documentation",
    "get_function_hash", "get_bulk_function_hashes", "get_function_labels",
    "list_classes", "list_class_members", "list_methods", "list_namespaces",
    # XRefs / Graphen
    "get_xrefs_to", "get_xrefs_from", "get_function_xrefs", "get_function_callees",
    "get_function_callers", "get_function_call_graph", "get_function_jump_targets",
    "get_full_call_graph", "analyze_call_graph",
    # Speicher / Daten / Strings
    "read_memory", "inspect_memory_content", "list_data_items", "list_data_items_by_xrefs",
    "list_strings", "search_strings", "search_instructions", "search_byte_patterns",
    "list_globals", "list_imports", "list_exports", "list_external_locations",
    "get_external_location", "get_entry_points", "list_bookmarks",
    # Analysen (nur lesend)
    "analyze_dataflow", "analyze_control_flow", "analyze_function_complete",
    "analyze_function_completeness", "analyze_for_documentation", "find_code_gaps",
    "find_dead_code", "find_next_undefined_function", "find_undocumented_by_string",
    "find_similar_functions", "find_similar_functions_fuzzy", "bulk_fuzzy_match",
    "diff_functions", "batch_string_anchor_report", "compare_programs_documentation",
    "get_function_call_graph", "audit_global", "audit_globals_in_function",
    # Typen (nur lesend)
    "list_data_types", "list_data_type_categories", "search_data_types",
    "get_valid_data_types", "validate_data_type", "validate_data_type_exists",
    "validate_function_prototype", "get_type_size", "get_struct_layout", "get_enum_values",
    "can_rename_at_address", "convert_number",
    # Kommentare lesen, Property-Maps lesen
    "get_comment", "get_plate_comment", "get_property", "list_properties",
    "list_property_maps",
]

# Schreibende Dokumentations-/Analysewerkzeuge (ghidra-standard), nicht zerstoererisch.
WRITE_ALLOW = [
    # Namen
    "rename_function", "rename_function_by_address", "rename_variable", "rename_variables",
    "rename_data", "rename_label", "rename_or_label", "rename_global_variable",
    "rename_data_type", "rename_external_location",
    # Kommentare
    "set_plate_comment", "set_comment", "set_disassembly_comment",
    "set_decompiler_comment", "batch_set_comments", "clear_function_comments",
    # Tags
    "add_function_tag", "batch_add_function_tags", "remove_function_tag",
    "batch_remove_function_tags", "create_function_tag", "set_function_tag_comment",
    # Funktionen
    "create_function", "set_function_prototype", "set_function_no_return",
    "set_function_this_type", "set_parameter_type", "set_local_variable_type",
    "set_variables", "set_decompiler_variable_type", "set_variable_storage",
    # Labels / Symbole
    "create_label", "batch_create_labels",
    # Datentypen (anlegen/aendern, nicht loeschen)
    "create_struct", "add_struct_field", "modify_struct_field", "modify_struct_field_type",
    "embed_struct_field", "create_enum", "create_typedef", "create_union",
    "create_pointer_type", "create_array_type", "clone_data_type",
    "apply_data_type", "apply_data_classification", "set_global", "import_data_types",
    "create_function_signature", "create_data_type_category", "move_data_type_to_category",
    # Lesezeichen / Referenzen (ruecknehmbar)
    "set_bookmark", "delete_bookmark", "add_memory_reference",
]


def load_names() -> tuple[list[str], list[str]]:
    data = json.loads(SCHEMA.read_text(encoding="utf-8"))
    entries = data if isinstance(data, list) else data.get("tools", [])
    gets, posts = [], []
    for e in entries:
        path = str(e.get("path", "")).strip()
        if not path.startswith("/"):
            continue
        name = path.lstrip("/").replace("/", "_")
        (gets if str(e.get("method", "")).upper() == "GET" else posts).append(name)
    return sorted(set(gets)), sorted(set(posts))


def build(profile: str, gets: list[str], posts: list[str]) -> dict:
    if profile == "none":
        return {
            "name": profile, "mcp": False, "groups": "", "builtins": "worker",
            "allowed": [], "denied": [], "writes_ghidra": False,
            "hard_denied": NEVER_ALLOW + HARD_DENY,
        }
    if profile == "ghidra-read":
        allowed = [n for n in READ_ALLOW if n in gets]
        writes = False
    elif profile == "ghidra-standard":
        allowed = [n for n in READ_ALLOW if n in gets] + [n for n in WRITE_ALLOW if n in posts]
        writes = True
    elif profile == "ghidra-full":
        allowed = [n for n in (gets + posts)]
        writes = True
    else:
        raise SystemExit(f"unbekanntes Profil: {profile}")

    deny = set(NEVER_ALLOW) | set(HARD_DENY)
    allowed = [n for n in dict.fromkeys(allowed) if n not in deny]
    denied = sorted((set(gets) | set(posts)) - set(allowed) - set(NEVER_ALLOW))
    return {
        "name": profile,
        "mcp": True,
        "groups": "listing,function,program",
        "builtins": "worker",
        "allowed": allowed,
        "denied": denied,
        "writes_ghidra": writes,
        "hard_denied": NEVER_ALLOW + HARD_DENY,
    }


def main() -> int:
    gets, posts = load_names()
    print(f"Katalog: {len(gets) + len(posts)} Werkzeuge ({len(gets)} GET, {len(posts)} POST)")
    missing = []
    for n in READ_ALLOW:
        if n not in gets:
            missing.append(("read", n, n in posts))
    for n in WRITE_ALLOW:
        if n not in posts:
            missing.append(("write", n, n in gets))
    if missing:
        print("NICHT im Katalog (bitte pruefen):")
        for where, n, other in missing:
            print(f"  - {where:<5} {n}" + ("   (steht in der anderen Methode)" if other else ""))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for profile in ("none", "ghidra-read", "ghidra-standard", "ghidra-full"):
        data = build(profile, gets, posts)
        p = OUT_DIR / f"{profile}.json"
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{p.name:<22} erlaubt={len(data['allowed']):>3}  gesperrt={len(data['denied']):>3}  "
              f"schreibt={data['writes_ghidra']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
