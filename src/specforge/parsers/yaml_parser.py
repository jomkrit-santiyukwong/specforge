from pathlib import Path
from ruamel.yaml import YAML
from specforge.models.spec import SpecFile


def load_spec(path: Path) -> SpecFile:
    yaml = YAML()
    with open(path, encoding="utf-8") as f:
        data = yaml.load(f)
    return SpecFile.model_validate(data)
