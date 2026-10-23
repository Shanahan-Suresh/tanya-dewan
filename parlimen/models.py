"""The two local models: Qwen3-Embedding (text to vector) and Qwen3-Reranker (question + passage
to one relevance score).

Both load on first use, on the GPU when it has room and on the CPU otherwise, and `unload()` gives
the memory back. The GPU is shared with Forge Neo, so nothing here holds it while idle.
"""
from __future__ import annotations

import gc
import time
from typing import Sequence

import numpy as np

from . import config

# Rough VRAM each model needs in float16, weights plus working room, in MB.
VRAM_NEED = {"0.6b": 2500, "4b": 10500}


def gpu_free_mb() -> int:
    """Free VRAM in MB, or 0 when there is no CUDA device."""
    import torch

    if not torch.cuda.is_available():
        return 0
    free, _total = torch.cuda.mem_get_info()
    return int(free / 2**20)


def pick_device(size: str, device: str | None = None) -> str:
    if device:
        return device
    return "cuda" if gpu_free_mb() >= VRAM_NEED[size] else "cpu"


def cached(model_id: str) -> bool:
    """True when the model is in the Hugging Face cache (HF_HOME), so loading it downloads nothing."""
    from huggingface_hub import try_to_load_from_cache

    return isinstance(try_to_load_from_cache(model_id, "config.json"), str)


def wait_for_gpu(size: str, timeout_s: float, poll_s: float = 30.0, log=print) -> bool:
    """Wait until the GPU has room for the model; False when the wait times out."""
    deadline = time.monotonic() + timeout_s
    while True:
        free = gpu_free_mb()
        if free >= VRAM_NEED[size]:
            return True
        if time.monotonic() >= deadline:
            return False
        log(f"GPU busy: {free} MB free, need {VRAM_NEED[size]} MB; checking again in {poll_s:.0f} s")
        time.sleep(poll_s)


def _model_kwargs(device: str) -> dict:
    """float16 on the GPU, bfloat16 on the CPU (half the memory, and Zen 4 runs it natively).

    On the GPU the weights stream straight to the card (`device_map`, through accelerate). Loading
    a 4B model through system RAM first committed 21 GB and starved the rest of the machine.
    """
    import torch

    if device == "cuda":
        return {"dtype": torch.float16, "device_map": "cuda"}
    return {"dtype": torch.bfloat16}


class Embedder:
    def __init__(self, size: str = "0.6b", device: str | None = None, max_tokens: int = 1024):
        self.size, self.model_id = size, config.EMBEDDERS[size]
        self._device, self.max_tokens = device, max_tokens
        self._model = None
        self.device = ""
        self._queries: dict[tuple[str, str], np.ndarray] = {}

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self.device = pick_device(self.size, self._device)
            self._model = SentenceTransformer(self.model_id, device=self.device,
                                              model_kwargs=_model_kwargs(self.device),
                                              processor_kwargs={"padding_side": "left"})
            self._model.max_seq_length = self.max_tokens
        return self._model

    def documents(self, texts: Sequence[str], batch_size: int = 16, progress: bool = False) -> np.ndarray:
        """Unit-length float32 vectors for passages (no instruction prefix)."""
        model = self._load()
        return model.encode(list(texts), batch_size=batch_size, normalize_embeddings=True,
                            convert_to_numpy=True, show_progress_bar=progress).astype(np.float32)

    def query(self, question: str, task: str = config.QUERY_TASK) -> np.ndarray:
        """Unit-length vector for a question, with Qwen3's instruction prefix.

        Vectors are kept, so the eval can embed every question first and unload the model before it
        loads a reranker: the 4B embedder and the 4B reranker do not fit on the GPU together.
        """
        key = (question, task)
        if key not in self._queries:
            model = self._load()
            vec = model.encode([question], prompt=f"Instruct: {task}\nQuery:", normalize_embeddings=True,
                               convert_to_numpy=True, show_progress_bar=False)
            self._queries[key] = vec[0].astype(np.float32)
        return self._queries[key]

    def unload(self) -> None:
        self._model = None
        _free()


class Reranker:
    """Qwen3-Reranker through sentence-transformers' CrossEncoder.

    The score is the model's yes-minus-no logit: above 0 leans relevant, and the gap between two
    passages is meaningful. A sigmoid would squash most good passages to 0.99. The instruction is
    the model card's default unless `task` is given: in a probe, the default kept a half-relevant
    passage further below the right one than a story-specific instruction did.
    """

    def __init__(self, size: str = "0.6b", device: str | None = None, max_tokens: int = 1024,
                 task: str | None = None):
        self.size, self.model_id = size, config.RERANKERS[size]
        self._device, self.max_tokens, self.task = device, max_tokens, task
        self._model = None
        self.device = ""

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self.device = pick_device(self.size, self._device)
            kw = {"prompts": {"query": self.task}, "default_prompt_name": "query"} if self.task else {}
            self._model = CrossEncoder(self.model_id, device=self.device, max_length=self.max_tokens,
                                       model_kwargs=_model_kwargs(self.device), **kw)
        return self._model

    def scores(self, question: str, passages: Sequence[str], batch_size: int = 8) -> list[float]:
        """Relevance logit of each passage for the question; higher is more relevant."""
        if not passages:
            return []
        model = self._load()
        logits = model.predict([(question, p) for p in passages], batch_size=batch_size,
                               show_progress_bar=False, convert_to_numpy=True)
        return np.asarray(logits, dtype=np.float64).tolist()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def unload(self) -> None:
        self._model = None
        _free()


def _free() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
