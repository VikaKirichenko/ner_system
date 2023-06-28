import os
from logging import getLogger
from pathlib import Path
from collections import defaultdict
from nltk.corpus import stopwords
from deeppavlov.core.models.serializable import Serializable
from deeppavlov.core.common.file import load_pickle, save_pickle
from deeppavlov.core.commands.utils import expand_path

log = getLogger(__name__)

class EntitiesParser(Serializable):
    def __init__(self, load_path: str = "~/.deeppavlov/downloads/wikidata_parse",
                 old_load_path: str = "~/.deeppavlov/downloads/entities",
                 save_path: str = "~/.deeppavlov/downloads/wikidata_rus",
                 word_to_idlist_filename: str = "word_to_idlist_vx.pickle",
                 entities_types_sets_filename: str = "entities_types_sets.pickle",
                 q_to_label_filename: str = "q_to_label_vx.pickle",
                 entities_ranking_dict_filename: str = "entities_ranking_dict_vx.pickle",
                 entities_descr_filename: str = "q_to_descr_vx.pickle",
                 types_dict_filename: str = "types_dict.pickle",
                 subclass_dict_filename: str = "subclass_dict.pickle",
                 log_filename: str = "/data/entities_parse_log.txt",
                 filter_tags: bool = True):

        super().__init__(save_path=save_path, load_path=load_path)
        old_load_path = str(expand_path(old_load_path))
        self.old_load_path = Path(old_load_path)
        self.wiki_dict = {}

        self.word_to_idlist_filename = word_to_idlist_filename
        self.entities_types_sets_filename = entities_types_sets_filename
        self.entities_ranking_dict_filename = entities_ranking_dict_filename
        self.entities_descr_filename = entities_descr_filename
        self.q_to_label_filename = q_to_label_filename
        self.types_dict_filename = types_dict_filename
        self.subclass_dict_filename = subclass_dict_filename
        self.log_filename = log_filename

        self.name_to_idlist = defaultdict(list)
        self.word_to_idlist = {}
        self.flat_list = []
        self.entities_ranking_dict = {}
        self.entities_descr = {}
        self.types_dict = {}
        self.subclass_dict = {}
        self.entities_types_sets = {"PER": set(), "LOC": set(), "ORG": set(), "AMB": set()}
        self.q_to_label = {}
        self.used_entities = set()
        self.filter_tags = filter_tags

        self.stopwords = set(stopwords.words("russian"))
        self.alphabet_full = set(
            " `abcdefghijklmnopqrstuvwxyzабвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789.,?!@#$%^&*()-+=\/№;:<>_–|")
        self.alphabet_full.add('"')
        self.alphabet_full.add("'")
        self.alphabet = set("abcdefghijklmnopqrstuvwxyzабвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789-")
        self.per_types = {"Q5"}
        self.loc_types = {"Q1048835", # political territorial entity
                          "Q15642541", # human-geographic territorial entity
                          "Q486972", # human settlement
                          "Q82794", # geographic region
                          "Q618123", # geographical object
                          "Q27096213", # geographic entity
                          "Q2221906", # geographic location
                          "Q56061", # administrative territorial entity
                          "Q337567", # still waters
                          "Q863944", # land waters
                          "Q271669", # landform
                          "Q2507626", # water area
                          "Q55659167", # natural watercourse
                          "Q355304", # watercourse
                          "Q35145263", # natural geographic object
                          "Q2015628", # open space
                          "Q294440" # public space
                         }

        self.org_types = {"Q43229", # organization
                          "Q11033" # mass media
                         }
        self.amb_types = {"Q41176" # building
                         }

    def load(self):
        self.load_path = str(expand_path(self.load_path))
        files = os.listdir(self.load_path)
        print(f"processed wikidata files for further parsing: {len(files)}", flush=True)
        for fl in files:
            wiki_chunk = load_pickle(self.load_path / Path(fl))
            self.wiki_dict.update(wiki_chunk)
        self.log_to_file("loaded wiki dict")
        print("loaded files", flush=True)
        self.word_to_idlist = load_pickle(self.old_load_path / self.word_to_idlist_filename)
        self.log_to_file("loaded word_to_idlist")
        self.entities_ranking_dict = load_pickle(self.old_load_path / self.entities_ranking_dict_filename)
        self.log_to_file("loaded entities_ranking_dict")
        self.entities_descr = load_pickle(self.old_load_path / self.entities_descr_filename)
        self.log_to_file("loaded entities_descr")
        self.entities_types_sets = load_pickle(self.old_load_path / self.entities_types_sets_filename)
        self.log_to_file("loaded entities_types_sets")
        self.q_to_label = load_pickle(self.old_load_path / self.q_to_label_filename)
        self.log_to_file("loaded q_to_label")
        self.types_dict = load_pickle(self.old_load_path / self.types_dict_filename)
        self.subclass_dict = load_pickle(self.old_load_path / self.subclass_dict_filename)
        self.log_to_file("loaded previous files")

    def save(self):
        save_pickle(self.word_to_idlist, self.save_path / self.word_to_idlist_filename)
        save_pickle(self.entities_ranking_dict, self.save_path / self.entities_ranking_dict_filename)
        save_pickle(self.entities_descr, self.save_path / self.entities_descr_filename)
        save_pickle(self.entities_types_sets, self.save_path / self.entities_types_sets_filename)
        save_pickle(self.q_to_label, self.save_path / self.q_to_label_filename)
        save_pickle(self.types_dict, self.save_path / self.types_dict_filename)
        save_pickle(self.subclass_dict, self.save_path / self.subclass_dict_filename)
        print("saved files", flush=True)
        
    def log_to_file(self, log_str):
        with open(self.log_filename, 'a') as out:
            out.write(str(log_str)+'\n')

    def parse(self):
        print(f"start parsing entities, entities_num {len(self.wiki_dict)}", flush=True)
        self.log_to_file(f"start parsing entities, entities_num {len(self.wiki_dict)}")
        for entity_type in self.entities_types_sets:
            self.used_entities = self.used_entities.union(self.entities_types_sets[entity_type])
        self.wiki_dict = {key: value for key, value in self.wiki_dict.items() if key in self.used_entities}
        self.log_to_file(f"new entities {len(self.wiki_dict)}")
        for entity_id in self.wiki_dict:
            entity_info = self.wiki_dict[entity_id]
            triplets = entity_info.get("triplets", [])
            for rel, *objects in triplets:
                if rel == "P31":
                    self.types_dict[entity_id] = set(objects)
                if rel == "P279":
                    self.subclass_dict[entity_id] = set(objects)
        print(f"parsed types_dict, {len(self.types_dict)} and subclass_dict, {len(self.subclass_dict)}", flush=True)
        
        entity_type_count = 0
        for entity_id in self.wiki_dict:
            entity_type = self.find(entity_id)
            entity_type_count += 1
            if entity_type_count%500000 == 0:
                print(f"parsed entity types {entity_type_count} used_entities {len(self.used_entities)}", flush=True)
                self.log_to_file(f"parsed entity types {entity_type_count} used_entities {len(self.used_entities)}")
            if entity_type:
                self.used_entities.add(entity_id)
                self.entities_types_sets[entity_type].add(entity_id)
        print(f"parsed used_entities and entities_types_sets {len(self.used_entities)}", flush=True)
        self.log_to_file(f"parsed used_entities and entities_types_sets {len(self.used_entities)}")
        
        for entity_id in self.wiki_dict:
            if entity_id in self.used_entities or not self.filter_tags:
                entity_info = self.wiki_dict[entity_id]
                name = entity_info.get("name", "")
                aliases = entity_info.get("aliases", [])
                if name:
                    self.name_to_idlist[name].append(entity_id)
                    if entity_id in self.q_to_label:
                        self.q_to_label[entity_id] += [name]
                    else:
                        self.q_to_label[entity_id] = [name]
                if aliases:
                    for alias in aliases:
                        self.name_to_idlist[alias].append(entity_id)
                        if entity_id in self.q_to_label:
                            self.q_to_label[entity_id] += [alias]
                triplets = entity_info.get("triplets", [])
                if triplets:
                    surname = self.find_surname(triplets)
                    if surname:
                        self.name_to_idlist[surname].append(entity_id)
                number_of_relations = entity_info.get("number_of_relations", 0)
                self.entities_ranking_dict[entity_id] = number_of_relations
        print("parsed name_to_idlist and entities_ranking_dict", flush=True)
        self.log_to_file("parsed name_to_idlist and entities_ranking_dict")

        for entity_id in self.wiki_dict:
            if entity_id in self.used_entities:
                entity_info = self.wiki_dict[entity_id]
                descr = entity_info.get("descr", "")
                triplets = entity_info.get("triplets", [])
                if not descr:
                    descr = self.find_descr(triplets)
                if descr:
                    self.entities_descr[entity_id] = descr

        for label in self.name_to_idlist:
            label_entities = self.name_to_idlist[label]
            self.add_label(label, label_entities)

    def add_label(self, label, entity_ids):
        label = label.lower()
        bad_symb = False
        for symb in label:
            if symb not in self.alphabet_full:
                bad_symb = True
                break
        if not bad_symb:
            label_split = label.split(' ')
            num_words = 0
            for label_elem in label_split:
                label_sanitized = ''.join([ch for ch in label_elem if ch in self.alphabet])
                if len(label_sanitized) > 1 and label_sanitized not in self.stopwords:
                    num_words += 1

            if num_words > 0:
                for label_elem in label_split:
                    label_sanitized = ''.join([ch for ch in label_elem if ch in self.alphabet])
                    if len(label_sanitized) > 1 and label_sanitized not in self.stopwords:
                        if label_sanitized not in self.word_to_idlist:
                            self.word_to_idlist[label_sanitized] = set()
                        for entity in entity_ids:
                            self.word_to_idlist[label_sanitized].add((entity, num_words))

    def find_descr(self, triplets):
        descr = ""
        for rel, *objects in triplets:
            if rel == "P31":
                for obj in objects:
                    if obj != "Q5":
                        obj_label = self.wiki_dict.get(obj, {}).get("name", "")
                        if obj_label:
                            return obj_label
            if rel == "P106":
                obj_label = self.wiki_dict.get(objects[0], {}).get("name", "")
                if obj_label:
                    return obj_label
        return descr
        
    def find_surname(self, triplets):
        surname = ""
        for rel, *objects in triplets:
            if rel == "P734":
                for obj in objects:
                    obj_label = self.wiki_dict.get(obj, {}).get("name", "")
                    if obj_label:
                        return obj_label
        return surname
        
    def find(self, entity):
        entity_type = ""
        prev_entities = {entity}
        for i in range(10):
            cur_entities = set()
            for entity in prev_entities:
                p31 = self.types_dict.get(entity, set())
                cur_entities = cur_entities.union(p31)
                p279 = self.subclass_dict.get(entity, set())
                cur_entities = cur_entities.union(p279)
            prev_entities = cur_entities
                
            if p31.intersection(self.per_types):
                return "PER"
            if p31.intersection(self.loc_types):
                return "LOC"
            if p31.intersection(self.org_types):
                return "ORG"
            if p31.intersection(self.amb_types):
                return "AMB"
            
            if p279.intersection(self.per_types):
                return "PER"
            if p279.intersection(self.loc_types):
                return "LOC"
            if p279.intersection(self.org_types):
                return "ORG"
            if p279.intersection(self.amb_types):
                return "AMB"
                    
        return ""
