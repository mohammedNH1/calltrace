"""Dataset access: catalogue, seeded sampling, download, and audio quality checks."""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from huggingface_hub import hf_hub_download

from .config import Config


@dataclass
class CallRecord:
    """Catalogue row for one call. `channels` maps channel number to its role and files."""

    source_id: str
    accent: str
    domain: str
    duration_s: float
    channels: dict[str, dict]
    merged_file: str
    n_reference_segments: int
    call_id: str = ""


class AppTekDataset:
    """Reads metadata from a pinned dataset revision and downloads only selected calls."""

    def __init__(self, config: Config):
        self.config = config
        self.repo_id = config["dataset"]["repo_id"]
        self.revision = config["dataset"]["revision"]
        self.raw_dir = config.path("raw_audio")
        self.manifest_dir = config.path("manifests")
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def _fetch(self, remote_path: str) -> Path:
        """Download one repository file at the pinned revision (cached on disk)."""
        return Path(
            hf_hub_download(
                self.repo_id,
                remote_path,
                repo_type="dataset",
                revision=self.revision,
                local_dir=self.raw_dir,
            )
        )

    def _read_metadata(self, config_dir: str, accent: str) -> list[dict]:
        path = self._fetch(f"{config_dir}/{accent}/metadata.jsonl")
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def build_catalogue(self) -> list[CallRecord]:
        """Join per-channel and merged metadata into one record per call."""
        catalogue: list[CallRecord] = []
        for accent in self.config["dataset"]["accents"]:
            # Group the two per-speaker channel rows of each conversation.
            channel_rows: dict[str, dict[str, dict]] = defaultdict(dict)
            for row in self._read_metadata("test", accent):
                match = re.search(r"([^/]+)_channel(\d+)\.wav$", row["file_name"])
                channel_rows[match.group(1)][match.group(2)] = {
                    "role": row["role"],
                    "speaker_id": row["speaker_id"],
                    "file": f"test/{accent}/{row['file_name']}",
                }
            for row in self._read_metadata("diarization", accent):
                source_id = Path(row["file_name"]).stem
                catalogue.append(
                    CallRecord(
                        source_id=source_id,
                        accent=accent,
                        domain=row["domain"],
                        duration_s=row["duration"],
                        channels=channel_rows.get(source_id, {}),
                        merged_file=f"diarization/{accent}/{row['file_name']}",
                        n_reference_segments=len(row["segments"]),
                    )
                )
        return catalogue

    def is_eligible(self, record: CallRecord) -> tuple[bool, str]:
        """Metadata-only eligibility check, applied before any transcript is seen."""
        roles = {channel["role"] for channel in record.channels.values()}
        if len(record.channels) != 2:
            return False, "does not have exactly two speaker channels"
        if roles != {"agent", "customer"}:
            return False, f"roles are not one agent and one customer: {sorted(roles)}"
        if record.duration_s < self.config["sampling"]["min_duration_s"]:
            return False, "shorter than the minimum duration"
        if record.n_reference_segments == 0:
            return False, "no reference segments"
        return True, ""

    def sample(self) -> dict:
        """Draw one call per accent with a fixed seed and record every exclusion.

        Rule: shuffle each accent's eligible calls (sorted first, so the order does
        not depend on file listing), then take the first call whose domain has not
        been used yet. If every domain is used, take the first call. Accents are
        visited in configured order. The rule looks only at metadata, never at
        transcripts or results, so easy calls cannot be hand-picked.
        """
        sampling = self.config["sampling"]
        rng = random.Random(sampling["seed"])
        catalogue = self.build_catalogue()

        by_accent: dict[str, list[CallRecord]] = defaultdict(list)
        exclusions = []
        for record in catalogue:
            eligible, reason = self.is_eligible(record)
            if eligible:
                by_accent[record.accent].append(record)
            else:
                exclusions.append({"source_id": record.source_id, "reason": reason})

        selected: list[CallRecord] = []
        used_domains: set[str] = set()
        pilot: CallRecord | None = None
        for accent in self.config["dataset"]["accents"]:
            pool = sorted(by_accent[accent], key=lambda r: r.source_id)
            rng.shuffle(pool)
            chosen = next((r for r in pool if r.domain not in used_domains), pool[0])
            used_domains.add(chosen.domain)
            chosen.call_id = f"{len(selected) + 1:03d}"
            selected.append(chosen)
            # The pilot comes from the same shuffled pool but is never part of the sample.
            if accent == sampling["pilot_accent"]:
                pilot = next(r for r in pool if r.source_id != chosen.source_id)
                pilot.call_id = "pilot"

        manifest = {
            "dataset": self.repo_id,
            "revision": self.revision,
            "license": self.config["dataset"]["license"],
            "seed": sampling["seed"],
            "rule": "one call per accent; seeded shuffle; first unused domain, else first call",
            "catalogue_calls": len(catalogue),
            "eligible_calls": sum(len(pool) for pool in by_accent.values()),
            "exclusions": exclusions,
            "selected": [asdict(record) for record in selected],
            "pilot": asdict(pilot) if pilot else None,
        }
        with open(self.manifest_dir / "sample_manifest.json", "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
        return manifest

    def load_manifest(self) -> dict:
        path = self.manifest_dir / "sample_manifest.json"
        if not path.exists():
            return self.sample()
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def download_call(self, record: dict) -> dict[str, Path]:
        """Fetch a call's two channels and the merged file used only for playback."""
        paths = {f"channel{ch}": self._fetch(info["file"]) for ch, info in record["channels"].items()}
        paths["merged"] = self._fetch(record["merged_file"])
        return paths

    def reference_segments(self, record: dict) -> list[dict]:
        """Manual reference segments. Kept apart from every ASR output."""
        rows = self._read_metadata("diarization", record["accent"])
        target = Path(record["merged_file"]).name
        return next(r for r in rows if Path(r["file_name"]).name == target)["segments"]

    def reference_channel_text(self, record: dict) -> dict[str, str]:
        """Manual per-channel reference transcript, keyed by channel number."""
        by_file = {
            f"test/{record['accent']}/{row['file_name']}": row["text"]
            for row in self._read_metadata("test", record["accent"])
        }
        return {ch: by_file[info["file"]] for ch, info in record["channels"].items()}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def audio_quality(path: Path) -> dict:
    """Basic checks on one audio file. Raises on unreadable or empty audio."""
    info = sf.info(str(path))
    audio, _ = sf.read(str(path), dtype="float32", always_2d=True)
    if audio.size == 0:
        raise ValueError(f"empty audio file: {path.name}")
    mono = audio[:, 0]
    # Short-window energy gives a rough speech share without a model.
    window = int(info.samplerate * 0.03)
    frames = mono[: len(mono) // window * window].reshape(-1, window)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    active = rms > 0.01
    return {
        "file": path.name,
        "samplerate": info.samplerate,
        "channels": info.channels,
        "duration_s": round(info.frames / info.samplerate, 3),
        "peak": round(float(np.abs(mono).max()), 4),
        "clipped_share": round(float(np.mean(np.abs(mono) >= 0.999)), 6),
        "active_share": round(float(active.mean()), 4),
        "noise_floor_rms": round(float(np.percentile(rms, 10)), 5),
        "speech_rms": round(float(np.percentile(rms[active], 50)) if active.any() else 0.0, 5),
        "sha256": sha256_of(path),
    }
