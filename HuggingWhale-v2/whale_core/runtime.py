from whale_core.config import Settings
from whale_core.providers import Generator, Voyage
from whale_core.service import Knowledge
from whale_core.storage import Atlas, Objects


def build(path="config.local.json"):
    cfg = Settings.load(path)
    return Knowledge(cfg, Atlas(cfg), Objects(cfg), Voyage(cfg), Generator(cfg))
