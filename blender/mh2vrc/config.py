# Run configuration for the MetaHuman -> VRChat bake.
#
# Every path the pipeline touches comes from here. The stages never hard-code a location: they
# call `get()` and read what the user put in their TOML file (see config.example.toml).

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ADDON_MODULE = "bl_ext.api_portal_polyhammer_com.character_dna"
TESTED_ADDON_VERSIONS = {(0, 12, 4)}

_active = None


@dataclass
class Config:
    config_path: Path
    head_dna: Path
    face_textures_dir: Path | None
    hair_fbx: Path | None
    eyebrow_fbx: Path | None
    work_dir: Path
    fbx_out: Path
    body_tri_target: int = 28000
    atlas_seed: int = 4242
    extra: dict = field(default_factory=dict)

    # Files the pipeline writes into work_dir. They are per-character and must never be
    # committed (the repo .gitignore blocks work/ for that reason).
    @property
    def checkpoint_blend(self) -> Path:
        return self.work_dir / "checkpoint_riglogic.blend"

    @property
    def stripped_blend(self) -> Path:
        return self.work_dir / "after_cleanup.blend"

    @property
    def merged_blend(self) -> Path:
        return self.work_dir / "merged.blend"

    @property
    def correctives_sidecar(self) -> Path:
        return self.work_dir / "corrective_shape_keys.json"

    @property
    def addon_poses(self) -> Path:
        return self.work_dir / "addon_poses_raw.json"

    @property
    def bake_result(self) -> Path:
        return self.work_dir / "bake_result.json"

    @property
    def reuv_result(self) -> Path:
        return self.work_dir / "hair_reuv_result.json"

    @property
    def verification(self) -> Path:
        return self.work_dir / "fbx_verification.json"

    @property
    def qa_dir(self) -> Path:
        return self.work_dir / "qa"

    @property
    def body_dna(self) -> Path:
        # The addon only looks for body.dna next to head.dna, so that is the only place we check.
        return self.head_dna.parent / "body.dna"


def _resolve(base: Path, value) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def load(config_path) -> Config:
    config_path = Path(config_path).resolve()
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    base = config_path.parent
    inputs = data.get("input", {})
    output = data.get("output", {})
    mesh = data.get("mesh", {})

    cfg = Config(
        config_path=config_path,
        head_dna=_resolve(base, inputs.get("head_dna")),
        face_textures_dir=_resolve(base, inputs.get("face_textures_dir")),
        hair_fbx=_resolve(base, inputs.get("hair_fbx")),
        eyebrow_fbx=_resolve(base, inputs.get("eyebrow_fbx")),
        work_dir=_resolve(base, output.get("work_dir", "work")),
        fbx_out=_resolve(base, output.get("fbx", "work/Avatar.fbx")),
        body_tri_target=int(mesh.get("body_tri_target", 28000)),
        atlas_seed=int(mesh.get("atlas_seed", 4242)),
        extra=data,
    )
    validate(cfg)
    return cfg


def validate(cfg: Config):
    problems = []
    if cfg.head_dna is None or not cfg.head_dna.is_file():
        problems.append(f"input.head_dna not found: {cfg.head_dna}")
    elif not cfg.body_dna.is_file():
        problems.append(f"body.dna must sit next to head.dna (looked for {cfg.body_dna})")
    for label, path in (("input.face_textures_dir", cfg.face_textures_dir),):
        if path is not None and not path.is_dir():
            problems.append(f"{label} is set but is not a folder: {path}")
    for label, path in (("input.hair_fbx", cfg.hair_fbx), ("input.eyebrow_fbx", cfg.eyebrow_fbx)):
        if path is not None and not path.is_file():
            problems.append(f"{label} is set but the file does not exist: {path}")
    if problems:
        raise SystemExit("Config errors:\n  " + "\n  ".join(problems))
    cfg.work_dir.mkdir(parents=True, exist_ok=True)
    cfg.fbx_out.parent.mkdir(parents=True, exist_ok=True)


def set_active(cfg: Config):
    global _active
    _active = cfg


def get() -> Config:
    if _active is None:
        raise RuntimeError("mh2vrc.config.set_active() has not been called - run through blender/run.py")
    return _active
