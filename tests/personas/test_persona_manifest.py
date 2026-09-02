import json
from pathlib import Path


def test_all_personas_are_synthetic_and_have_four_variants() -> None:
    path = Path(__file__).parents[2] / "packages" / "evaluation" / "personas.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["source"] == "synthetic"
    assert len(manifest["personas"]) == 7
    assert len(manifest["variants_per_persona"]) == 4


def test_honest_beginner_is_protected_from_false_accusation() -> None:
    path = Path(__file__).parents[2] / "packages" / "evaluation" / "personas.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    p5 = next(persona for persona in manifest["personas"] if persona["id"] == "P5")
    assert "exposed_contradiction=0" in p5["assertions"]
    assert "honesty_label_absent=true" in p5["assertions"]


