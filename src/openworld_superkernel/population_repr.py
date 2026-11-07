"""Experimental distribution sketch and *typed* agent genome.

This module is a CPU-only mathematical fixture. Neither the sketch nor genome
grants identity, permissions, learned intelligence, or source verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import random
from collections.abc import Iterable, Mapping, Sequence

SCHEMA = "openworld.agent-genome.research.v0"
ROLES = frozenset({"explorer", "builder", "trader", "diplomat", "researcher"})
POLICY_FAMILIES = frozenset({"rules", "shared-mlp", "external-policy"})
TRAITS = frozenset({"curiosity", "cooperation", "risk", "patience"})


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                             allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def _digest(value: str) -> bool:
    return (isinstance(value, str) and value.startswith("sha256:")
            and len(value) == 71
            and all(c in "0123456789abcdef" for c in value[7:]))


@dataclass(frozen=True)
class AgentGenome:
    """Immutable research genotype; never store identity, secret, memory or weights."""

    role: str
    policy_family: str
    policy_digest: str
    traits: tuple[tuple[str, int], ...]
    generation: int
    parent_genome_id: str | None
    genome_id: str

    def __post_init__(self) -> None:
        if (self.role not in ROLES or self.policy_family not in POLICY_FAMILIES
                or not _digest(self.policy_digest)
                or type(self.generation) is not int or self.generation < 0):
            raise ValueError("invalid genome schema or policy reference")
        if (type(self.traits) is not tuple or not self.traits
                or tuple(name for name, _ in self.traits) !=
                tuple(sorted(name for name, _ in self.traits))
                or len(set(name for name, _ in self.traits)) != len(self.traits)
                or any(name not in TRAITS or type(v) is not int or not 0 <= v <= 100
                       for name, v in self.traits)):
            raise ValueError("invalid or noncanonical traits")
        if (self.generation == 0) != (self.parent_genome_id is None):
            raise ValueError("genome lineage mismatch")
        if self.parent_genome_id is not None and not _digest(self.parent_genome_id):
            raise ValueError("invalid parent digest")
        fields = [SCHEMA, self.role, self.policy_family, self.policy_digest,
                  self.traits, self.generation, self.parent_genome_id]
        if self.genome_id != "sha256:" + _hash(fields):
            raise ValueError("genome ID does not match content")


def make_genome(role: str, policy_family: str, policy_digest: str,
                traits: Mapping[str, int],
                *, parent: AgentGenome | None = None) -> AgentGenome:
    """Content addressed genome blueprint; not an authorization or a new agent."""
    if not isinstance(traits, Mapping):
        raise TypeError("traits must be a mapping")
    ordered = tuple(sorted(traits.items()))
    generation = 0 if parent is None else parent.generation + 1
    parent_id = None if parent is None else parent.genome_id
    fields = [SCHEMA, role, policy_family, policy_digest, ordered,
              generation, parent_id]
    return AgentGenome(role, policy_family, policy_digest, ordered, generation,
                       parent_id, "sha256:" + _hash(fields))


def mutate_genome(genome: AgentGenome, *, seed: int, step: int = 5) -> AgentGenome:
    """One bounded offline trait edit. Admission, fitness and policy are separate."""
    if not isinstance(genome, AgentGenome) or type(seed) is not int or seed < 0:
        raise ValueError("invalid parent or seed")
    if type(step) is not int or not 1 <= step <= 25:
        raise ValueError("mutation step out of range")
    rng = random.Random(seed)
    traits = dict(genome.traits)
    name = rng.choice(tuple(sorted(traits)))
    old = traits[name]
    direction = -1 if rng.randrange(2) == 0 else 1
    if not 0 <= old + direction * step <= 100:
        direction *= -1
    traits[name] = old + direction * step
    return make_genome(genome.role, genome.policy_family, genome.policy_digest,
                       traits, parent=genome)


def _vector(value: Sequence[float], *, dim: int | None = None) -> tuple[float, ...]:
    if not isinstance(value, (tuple, list)) or not value or len(value) > 16:
        raise ValueError("feature vectors must have dimension 1..16")
    if dim is not None and len(value) != dim:
        raise ValueError("incompatible feature dimensions")
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in value):
        raise ValueError("nonfinite or nonnumeric feature")
    return tuple(float(v) for v in value)


def empirical_cf(samples: Sequence[Sequence[float]],
                 frequency: Sequence[float]) -> tuple[float, float]:
    """Empirical characteristic function (real, imaginary): E[exp(i w dot X)].

    At FINITELY many frequencies it is a *lossy signature*. No density inversion
    or independence assumption follows from the signature.
    """
    if not samples:
        raise ValueError("no samples")
    w = _vector(frequency)
    vectors = tuple(_vector(x, dim=len(w)) for x in samples)
    phases = (math.fsum(a*b for a, b in zip(w, x)) for x in vectors)
    values = tuple((math.cos(p), math.sin(p)) for p in phases)
    return (math.fsum(v[0] for v in values) / len(values),
            math.fsum(v[1] for v in values) / len(values))


@dataclass(frozen=True)
class PopulationPoint:
    role: str
    region: str
    features: tuple[float, ...]


@dataclass(frozen=True)
class PopulationSketch:
    """Group summary only; no individual ownership, identity or exact history."""

    role: str
    region: str
    count: int
    frequencies: tuple[tuple[float, ...], ...]
    characteristic: tuple[tuple[float, float], ...]


def sketch_population(points: Iterable[PopulationPoint],
                      frequencies: Sequence[Sequence[float]],
                      *, min_group_size: int = 2) -> tuple[PopulationSketch, ...]:
    """Stratified mean-field ECF, bounded K and feature dimension.

    The N*K*d arithmetic costs exclude input parsing and allocation. Small
    groups are omitted but this is NOT differential privacy or k-anonymity.
    """
    if type(min_group_size) is not int or min_group_size < 2:
        raise ValueError("min_group_size must be at least 2")
    if not isinstance(frequencies, (tuple, list)) or not 1 <= len(frequencies) <= 64:
        raise ValueError("expected 1..64 frequencies")
    omegas = tuple(_vector(f) for f in frequencies)
    dim = len(omegas[0])
    if any(len(f) != dim for f in omegas):
        raise ValueError("frequency dimensions mismatch")
    groups: dict[tuple[str, str], list[tuple[float, ...]]] = {}
    for point in points:
        if not isinstance(point, PopulationPoint) or point.role not in ROLES:
            raise ValueError("invalid population point")
        if not isinstance(point.region, str) or not point.region:
            raise ValueError("invalid region")
        groups.setdefault((point.role, point.region), []).append(
            _vector(point.features, dim=dim))
    return tuple(
        PopulationSketch(role, region, len(vectors), omegas,
                         tuple(empirical_cf(vectors, f) for f in omegas))
        for (role, region), vectors in sorted(groups.items())
        if len(vectors) >= min_group_size
    )
