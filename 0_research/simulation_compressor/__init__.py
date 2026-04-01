from dataclasses import dataclass


@dataclass
class CFDImage:
    name: str
    path: str
    plane: str
    index: int


FILE_MAPPING = {
    'XX': r"X(\d+)X\.png",
    'YY': r"Y(\d+)Y\.png",
    'ZZ': r"Z(\d+)Z\.png",
}
