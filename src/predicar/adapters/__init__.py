"""Research-area catalogues for PREDICAR; adapters do not execute on import."""

from .constraint_programming import AREA as CONSTRAINT_PROGRAMMING
from .error_correcting import AREA as ERROR_CORRECTING
from .neural_population import AREA as NEURAL_POPULATION
from .point_processes import AREA as POINT_PROCESSES
from .rfs_tracking import AREA as RFS_TRACKING
from .statistical_physics import AREA as STATISTICAL_PHYSICS

ALL_AREAS = (
    RFS_TRACKING,
    NEURAL_POPULATION,
    STATISTICAL_PHYSICS,
    ERROR_CORRECTING,
    POINT_PROCESSES,
    CONSTRAINT_PROGRAMMING,
)

__all__ = [
    "ALL_AREAS",
    "CONSTRAINT_PROGRAMMING",
    "ERROR_CORRECTING",
    "NEURAL_POPULATION",
    "POINT_PROCESSES",
    "RFS_TRACKING",
    "STATISTICAL_PHYSICS",
]
