from pydantic import Field
from typing import Literal

class Split(Split):
    speed: float = Field(default=1.0, ge=0.5, le=4.0, allow_inf_nan=False)
    match_main_width: bool = True
    fill_frame: bool = True
    mirror: bool = False
    files: list[str] = Field(default_factory=list)
    bouncing_ball: bool = False

class Montage(Montage):
    split: Split = Field(default_factory=Split)
    mirror_main: bool = False
    main_framing: Literal['blur', 'crop'] = 'blur'
    main_scale: float = Field(default=1.0, ge=0.5, le=1.0, allow_inf_nan=False)


_check_legacy_files = check_files


def check_files(template):
    split = template.split
    if not split.enabled or not (split.files or split.bouncing_ball):
        return _check_legacy_files(template)
    for path in split.files:
        if not path or not Path(path).is_file():
            raise ValueError(f'Дополнительное видео не найдено: {path}')
    without_split = split.model_copy(update={'enabled': False})
    return _check_legacy_files(template.model_copy(update={'split': without_split}))
