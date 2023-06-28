from os import getenv
from pathlib import Path

DATA_PATH = Path(getenv('DATA_PATH', '/data')).resolve()
DOWNLOADS_PATH = Path('/data/downloads').resolve()
HOST_DATA_PATH = Path(getenv('HOST_DATA_PATH', '~/data')).resolve()

WIKIDATA_PATH = DATA_PATH / 'wikidata.json.bz2'
WIKIDATA_URL = 'https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2'

PARSED_WIKIDATA_PATH = DATA_PATH / 'parsed_wikidata'
PARSED_WIKIDATA_OLD_PATH = DATA_PATH / 'parsed_wikidata_old'
PARSED_WIKIDATA_NEW_PATH = DATA_PATH / 'parsed_wikidata_new'

ENTITIES_PATH = DATA_PATH / 'entities'
ENTITIES_OLD_PATH = DATA_PATH / 'entities_old'
ENTITIES_NEW_PATH = DATA_PATH / 'entities_new'

FAISS_PATH = DATA_PATH / 'faiss'
FAISS_OLD_PATH = DATA_PATH / 'faiss_old'
FAISS_NEW_PATH = DATA_PATH / 'faiss_new'

STATE_PATH = DATA_PATH / 'state.yaml'
ALIASES_PATH = DATA_PATH / 'aliases.pickle'
CONTAINERS_CONFIG_PATH = DATA_PATH / 'containers.yaml'
LOGS_PATH = DATA_PATH / 'logs'

METRICS_FILENAME = DATA_PATH / "metrics_score_history.csv"

LOCKFILE = DATA_PATH / 'lockfile'
