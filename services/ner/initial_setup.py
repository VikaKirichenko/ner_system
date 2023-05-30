from pathlib import Path
from shutil import copytree

from deeppavlov.core.commands.utils import parse_config

from main import LOG_PATH


def initial_setup():
    if not LOG_PATH.exists():
        LOG_PATH.mkdir(parents=True)
    config = parse_config('entity_detection.json')
    model_path = config['metadata']['variables']['NER_PATH']
    init_path = next(
        i for i in config['metadata']['download'] if 'ner_rus_bert_torch_new.tar.gz' in i['url']
    )['subdir']
    if not Path(model_path).exists():
        copytree(init_path, model_path)
