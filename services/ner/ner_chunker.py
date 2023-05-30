# Copyright 2017 Neural Networks and Deep Learning lab, MIPT
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import time
from logging import getLogger
from string import punctuation
from typing import List, Tuple, Any

import pymorphy2
from deeppavlov.core.commands.utils import expand_path
from deeppavlov.core.common.chainer import Chainer
from deeppavlov.core.common.registry import register
from deeppavlov.core.models.component import Component
from deeppavlov.models.kbqa.entity_detection_parser import EntityDetectionParser
from deeppavlov.models.tokenizers.utils import detokenize
from nltk import sent_tokenize
from transformers import AutoTokenizer

log = getLogger(__name__)


@register('ner_chunker')
class NerChunker(Component):
    """
        Class to split documents into chunks of max_chunk_len symbols so that the length will not exceed
        maximal sequence length to feed into BERT
    """

    def __init__(self, vocab_file: str, max_seq_len: int = 400, lowercase: bool = False, max_chunk_len: int = 180,
                 batch_size: int = 2, **kwargs):
        """

        Args:
            max_chunk_len: maximal length of chunks into which the document is split
            batch_size: how many chunks are in batch
        """
        self.max_seq_len = max_seq_len
        self.max_chunk_len = max_chunk_len
        self.batch_size = batch_size
        self.re_tokenizer = re.compile(r"[\w']+|[^\w ]")
        vocab_file = str(expand_path(vocab_file))
        self.tokenizer = AutoTokenizer.from_pretrained(vocab_file,
                                                       do_lower_case=True)
        self.punct_ext = punctuation + " " + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        self.russian_letters = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        self.lowercase = lowercase

    def __call__(self, docs_batch: List[str]) -> Tuple[List[List[str]], List[List[int]]]:
        """
        This method splits each document in the batch into chunks wuth the maximal length of max_chunk_len
 
        Args:
            docs_batch: batch of documents

        Returns:
            batch of lists of document chunks for each document
            batch of lists of numbers of documents which correspond to chunks
        """
        text_batch_list = []
        text_batch = []
        nums_batch_list = []
        nums_batch = []
        sentences_offsets_batch_list = []
        sentences_offsets_batch = []
        sentences_batch_list = []
        sentences_batch = []

        for n, doc in enumerate(docs_batch):
            if self.lowercase:
                doc = doc.lower()
            start = 0
            text = ""
            sentences_list = []
            sentences_offsets_list = []
            cur_len = 0
            doc_pieces = doc.split("\n")
            doc_pieces = [self.sanitize(doc_piece) for doc_piece in doc_pieces]
            doc_pieces = [doc_piece for doc_piece in doc_pieces if len(doc_piece) > 1]
            if doc_pieces:
                sentences = []
                for doc_piece in doc_pieces:
                    sentences += sent_tokenize(doc_piece)
                for sentence in sentences:
                    sentence_tokens = re.findall(self.re_tokenizer, sentence)
                    sentence_len = sum(
                        [len(self.tokenizer.encode_plus(token, add_special_tokens=False)["input_ids"]) for token in
                         sentence_tokens])
                    if cur_len + sentence_len < self.max_seq_len:
                        text += f"{sentence} "
                        cur_len += sentence_len
                        end = start + len(sentence)
                        sentences_offsets_list.append((start, end))
                        sentences_list.append(sentence)
                        start = end + 1
                    else:
                        text = text.strip()
                        if text:
                            text_batch.append(text)
                            sentences_offsets_batch.append(sentences_offsets_list)
                            sentences_batch.append(sentences_list)
                            nums_batch.append(n)

                        if sentence_len < self.max_seq_len:
                            text = f"{sentence} "
                            cur_len = sentence_len
                            start = 0
                            end = start + len(sentence)
                            sentences_offsets_list = [(start, end)]
                            sentences_list = [sentence]
                            start = end + 1
                        else:
                            text = ""
                            if "," in sentence:
                                sentence_chunks = sentence.split(", ")
                                for chunk in sentence_chunks:
                                    chunk_tokens = re.findall(self.re_tokenizer, chunk)
                                    chunk_len = sum(
                                        [len(self.tokenizer.encode_plus(token, add_special_tokens=False)["input_ids"])
                                         for token in chunk_tokens])
                                    if cur_len + chunk_len < self.max_seq_len:
                                        text += f"{chunk}, "
                                        cur_len += chunk_len + 1
                                        end = start + len(chunk) + 1
                                        sentences_offsets_list.append((start, end))
                                        sentences_list.append(f"{chunk},")
                                        start = end + 1
                                    else:
                                        text = text.strip().strip(",")
                                        if text:
                                            text_batch.append(text)
                                            sentences_offsets_batch.append(sentences_offsets_list)
                                            sentences_batch.append(sentences_list)
                                            nums_batch.append(n)

                                        if chunk_len < self.max_seq_len:
                                            text = f"{chunk}, "
                                            cur_len = chunk_len
                                            start = 0
                                            end = start + len(chunk) + 1
                                            sentences_offsets_list = [(start, end)]
                                            sentences_list = [f"{chunk},"]
                                            start = end + 1
                                        else:
                                            new_sentence_chunks = sentence.split(" ")
                                            for new_chunk in new_sentence_chunks:
                                                new_chunk_tokens = re.findall(self.re_tokenizer, new_chunk)
                                                new_chunk_len = sum([len(
                                                    self.tokenizer.encode_plus(token, add_special_tokens=False)[
                                                        "input_ids"]) for token in new_chunk_tokens])
                                                if cur_len + new_chunk_len < self.max_seq_len:
                                                    text = f"{new_chunk} "
                                                    cur_len = new_chunk_len
                                                    start = 0
                                                    end = start + len(new_chunk)
                                                    sentences_offsets_list.append((start, end))
                                                    sentences_list.append(new_chunk)
                                                    start = end + 1
                                                else:
                                                    text = text.strip()
                                                    if text:
                                                        text_batch.append(text)
                                                        sentences_offsets_batch.append(sentences_offsets_list)
                                                        sentences_batch.append(sentences_list)
                                                        nums_batch.append(n)

                                                    text = f"{new_chunk} "
                                                    cur_len = new_chunk_len
                                                    start = 0
                                                    end = start + len(new_chunk)
                                                    sentences_offsets_list = [(start, end)]
                                                    sentences_list = [new_chunk]
                                                    start = end + 1
                            else:
                                sentence_chunks = sentence.split(" ")
                                for chunk in sentence_chunks:
                                    chunk_tokens = re.findall(self.re_tokenizer, chunk)
                                    chunk_len = sum(
                                        [len(self.tokenizer.encode_plus(token, add_special_tokens=False)["input_ids"])
                                         for token in chunk_tokens])
                                    if cur_len + chunk_len < self.max_seq_len:
                                        text += f"{chunk} "
                                        cur_len += chunk_len + 1
                                        end = start + len(chunk)
                                        sentences_offsets_list.append((start, end))
                                        sentences_list.append(chunk)
                                        start = end + 1
                                    else:
                                        text = text.strip()
                                        if text:
                                            text_batch.append(text)
                                            sentences_offsets_batch.append(sentences_offsets_list)
                                            sentences_batch.append(sentences_list)
                                            nums_batch.append(n)

                                        text = f"{chunk} "
                                        cur_len = chunk_len
                                        start = 0
                                        end = start + len(chunk)
                                        sentences_offsets_list = [(start, end)]
                                        sentences_list = [chunk]
                                        start = end + 1

                text = text.strip().strip(",")
                if text:
                    text_batch.append(text)
                    nums_batch.append(n)
                    sentences_offsets_batch.append(sentences_offsets_list)
                    sentences_batch.append(sentences_list)
            else:
                text_batch.append("а")
                nums_batch.append(n)
                sentences_offsets_batch.append([(0, len(doc))])
                sentences_batch.append([doc])

        num_batches = len(text_batch) // self.batch_size + int(len(text_batch) % self.batch_size > 0)
        for jj in range(num_batches):
            text_batch_list.append(text_batch[jj * self.batch_size:(jj + 1) * self.batch_size])
            nums_batch_list.append(nums_batch[jj * self.batch_size:(jj + 1) * self.batch_size])
            sentences_offsets_batch_list.append(
                sentences_offsets_batch[jj * self.batch_size:(jj + 1) * self.batch_size])
            sentences_batch_list.append(sentences_batch[jj * self.batch_size:(jj + 1) * self.batch_size])

        return text_batch_list, nums_batch_list, sentences_offsets_batch_list, sentences_batch_list

    def sanitize(self, text):
        text_len = len(text)

        if text_len > 0 and text[text_len - 1] not in {'.', '!', '?'}:
            i = text_len - 1
            while text[i] in self.punct_ext and i > 0:
                i -= 1
                if (text[i] in {'.', '!', '?'} and text[i - 1].lower() in self.russian_letters) or \
                        (i > 1 and text[i] in {'.', '!', '?'} and text[i - 1] in '"' and text[
                            i - 2].lower() in self.russian_letters):
                    break

            text = text[:i + 1]
        text = re.sub(r'\s+', ' ', text)
        return text


@register('ner_chunk_model')
class NerChunkModel(Component):
    """
        Class for linking of entity substrings in the document to entities in Wikidata
    """

    def __init__(self, ner: Chainer,
                 ner_parser: EntityDetectionParser,
                 lemmatize: bool = False,
                 **kwargs) -> None:
        """

        Args:
            ner: config for entity detection
            ner_parser: component deeppavlov.models.kbqa.entity_detection_parser
            **kwargs:
        """
        self.ner = ner
        self.ner_parser = ner_parser

    def __call__(self, text_batch_list: List[List[str]],
                 nums_batch_list: List[List[int]],
                 sentences_offsets_batch_list: List[List[List[Tuple[int, int]]]],
                 sentences_batch_list: List[List[List[str]]]
                 ):
        """

        Args:
            text_batch_list: list of document chunks
            nums_batch_list: nums of documents
            sentences_offsets_batch_list: indices of start and end symbols of sentences in text
            sentences_batch_list: list of sentences from texts
        Returns:
            doc_entity_substr_batch: entity substrings
            doc_entity_offsets_batch: indices of start and end symbols of entities in text
            doc_tags_batch: entity tags (PER, LOC, ORG)
            doc_sentences_offsets_batch: indices of start and end symbols of sentences in text
            doc_sentences_batch: list of sentences from texts
        
        Examples of input arguments:
            text_batch_list: [['Екатеринбург - город в России, административный центр Уральского федерального 
                                округа и Свердловской области. Расположен на восточном склоне Среднего Урала,
                                по берегам реки Исети.']]
            nums_batch_list: [[0]]
            sentences_offsets_batch_list: [[[(0, 108), (109, 178)]]]
            sentences_batch_list: [[['Екатеринбург - город в России, административный центр Уральского федерального
                                      округа и Свердловской области.',
                                      'Расположен на восточном склоне Среднего Урала, по берегам реки Исети.']]]
        
        Examples of outputs:
            doc_entity_substr_batch: [['екатеринбург', 'россии', 'уральского федерального округа',
                                       'свердловской области', 'среднего урала', 'исети']]
            doc_entity_offsets_batch: [[(0, 12), (23, 29), (54, 84), (87, 107), (140, 154), (172, 177)]]
            doc_tags_batch: [['LOC', 'LOC', 'LOC', 'LOC', 'LOC', 'LOC']]
            doc_sentences_offsets_batch: [[(0, 108), (109, 178)]]
            doc_sentences_batch: [['Екатеринбург - город в России, административный центр Уральского федерального
                                    округа и Свердловской области.',
                                    'Расположен на восточном склоне Среднего Урала, по берегам реки Исети.']]
        """
        entity_substr_batch_list = []
        entity_offsets_batch_list = []
        tags_batch_list = []
        entity_probas_batch_list = []
        text_len_batch_list = []
        status_batch = []
        for text_batch, sentences_offsets_batch, sentences_batch in \
                zip(text_batch_list, sentences_offsets_batch_list, sentences_batch_list):
            tm_ner_st = time.time()
            text_batch = [text.replace("\xad", " ") for text in text_batch]
            status = "ok"
            try:
                ner_tokens_batch, ner_tokens_offsets_batch, ner_probas_batch, probas_batch = self.ner(text_batch)
                entity_substr_batch, entity_positions_batch, entity_probas_batch = \
                    self.ner_parser(ner_tokens_batch, ner_probas_batch, probas_batch)
            except:
                entity_substr_batch = [{} for _ in text_batch]
                entity_positions_batch = [{} for _ in text_batch]
                entity_probas_batch = [{} for _ in text_batch]
                status = "error"

            tm_ner_end = time.time()
            log.debug(f"ner time {tm_ner_end - tm_ner_st}")
            log.debug(f"entity_substr_batch {entity_substr_batch}")
            log.debug(f"entity_positions_batch {entity_positions_batch}")
            entity_pos_tags_probas_batch = [[(entity_substr.lower(), entity_substr_positions, tag, entity_proba)
                                             for tag, entity_substr_list in entity_substr_dict.items()
                                             for entity_substr, entity_substr_positions, entity_proba in
                                             zip(entity_substr_list, entity_positions_dict[tag],
                                                 entity_probas_dict[tag])]
                                            for entity_substr_dict, entity_positions_dict, entity_probas_dict in
                                            zip(entity_substr_batch, entity_positions_batch, entity_probas_batch)]
            entity_substr_batch = []
            entity_offsets_batch = []
            tags_batch = []
            probas_batch = []
            for entity_pos_tags_probas, ner_tokens_offsets_list in \
                    zip(entity_pos_tags_probas_batch, ner_tokens_offsets_batch):
                if entity_pos_tags_probas:
                    entity_offsets_list = []
                    entity_substr_list, entity_positions_list, tags_list, probas_list = zip(*entity_pos_tags_probas)
                    for entity_positions in entity_positions_list:
                        start_offset = ner_tokens_offsets_list[entity_positions[0]][0]
                        end_offset = ner_tokens_offsets_list[entity_positions[-1]][1]
                        entity_offsets_list.append((start_offset, end_offset))
                else:
                    entity_substr_list, entity_offsets_list, tags_list, probas_list = [], [], [], []
                entity_substr_batch.append(list(entity_substr_list))
                entity_offsets_batch.append(list(entity_offsets_list))
                tags_batch.append(list(tags_list))
                probas_batch.append(list(probas_list))

            log.debug(f"entity_substr_batch {entity_substr_batch}")
            log.debug(f"entity_offsets_batch {entity_offsets_batch}")

            entity_substr_batch_list.append(entity_substr_batch)
            tags_batch_list.append(tags_batch)
            entity_offsets_batch_list.append(entity_offsets_batch)
            entity_probas_batch_list.append(probas_batch)
            text_len_batch_list.append([len(text) for text in text_batch])
            status_batch.append(status)

        doc_entity_substr_batch, doc_tags_batch, doc_entity_offsets_batch, doc_probas_batch = [], [], [], []
        doc_sentences_offsets_batch, doc_sentences_batch, doc_status_batch = [], [], []
        doc_entity_substr, doc_tags, doc_probas, doc_entity_offsets = [], [], [], []
        doc_sentences_offsets, doc_sentences = [], []
        cur_doc_num = 0
        text_len_sum = 0
        for entity_substr_batch, tags_batch, probas_batch, entity_offsets_batch, sentences_offsets_batch, \
            sentences_batch, text_len_batch, nums_batch, status in \
                zip(entity_substr_batch_list, tags_batch_list, entity_probas_batch_list, entity_offsets_batch_list,
                    sentences_offsets_batch_list, sentences_batch_list, text_len_batch_list, nums_batch_list,
                    status_batch):
            for entity_substr_list, tag_list, probas_list, entity_offsets_list, sentences_offsets_list, \
                sentences_list, text_len, doc_num in \
                    zip(entity_substr_batch, tags_batch, probas_batch, entity_offsets_batch, sentences_offsets_batch,
                        sentences_batch, text_len_batch, nums_batch):
                if doc_num == cur_doc_num:
                    doc_entity_substr += entity_substr_list
                    doc_tags += tag_list
                    doc_probas += probas_list
                    doc_entity_offsets += [(start_offset + text_len_sum, end_offset + text_len_sum)
                                           for start_offset, end_offset in entity_offsets_list]
                    doc_sentences_offsets += [(start_offset + text_len_sum, end_offset + text_len_sum)
                                              for start_offset, end_offset in sentences_offsets_list]
                    doc_sentences += sentences_list
                    text_len_sum += text_len + 1
                    cur_status = status
                else:
                    doc_entity_substr_batch.append(doc_entity_substr)
                    doc_tags_batch.append(doc_tags)
                    doc_probas_batch.append(doc_probas)
                    doc_entity_offsets_batch.append(doc_entity_offsets)
                    doc_sentences_offsets_batch.append(doc_sentences_offsets)
                    doc_sentences_batch.append(doc_sentences)
                    doc_status_batch.append(cur_status)
                    doc_entity_substr = entity_substr_list
                    doc_tags = tag_list
                    doc_probas = probas_list
                    doc_entity_offsets = entity_offsets_list
                    doc_sentences_offsets = sentences_offsets_list
                    doc_sentences = sentences_list
                    cur_doc_num = doc_num
                    text_len_sum = text_len + 1

        doc_entity_substr_batch.append(doc_entity_substr)
        doc_tags_batch.append(doc_tags)
        doc_probas_batch.append(doc_probas)
        doc_entity_offsets_batch.append(doc_entity_offsets)
        doc_sentences_offsets_batch.append(doc_sentences_offsets)
        doc_sentences_batch.append(doc_sentences)
        doc_status_batch.append(cur_status)

        return doc_entity_substr_batch, doc_entity_offsets_batch, doc_tags_batch, \
               doc_sentences_offsets_batch, doc_sentences_batch, doc_probas_batch, doc_status_batch


@register('ner_postprocessor')
class NerPostprocessor:
    def __init__(self, lemmatize: bool = False, **kwargs):
        self.morph = pymorphy2.MorphAnalyzer()
        self.lemmatize = lemmatize

    def __call__(self, text_batch: List[str], entity_substr_batch: List[List[str]],
                 entity_offsets_batch: List[List[List[int]]], entity_tags_batch: List[List[str]],
                 sentences_batch: List[List[str]], entity_probas_batch: List[List[Any]]):
        replace_list = [(" ' ", ' "'), (" '", '"'), ("' ", '"'), ("« ", "«"), (" »", "»"), ("- ", "-"), (" -", "-"),
                        (" ’ s", "’s"), ("( ", "("), (" )", ")"), ("{ ", "{"), (" }", "}"), (" :", ":"), ("№ ", "№"),
                        (" ,", ","), ("  ", " ")]
        delete_list = [("{", ''), ("}", ''), ("(", ' '), (")", ' '), ("  ", " ")]
        new_entity_substr_batch = []
        new_entity_lemm_substr_batch = []
        new_entity_offsets_batch = []
        new_entity_init_offsets_batch = []
        new_entity_tags_batch = []
        new_entity_probas_batch = []
        for entity_substr_list, text, sentences_list, entity_offsets_list, entity_tags_list, entity_probas_list in \
                zip(entity_substr_batch, text_batch, sentences_batch, entity_offsets_batch, entity_tags_batch,
                    entity_probas_batch):
            entity_info = list(zip(entity_substr_list, entity_offsets_list, entity_tags_list, entity_probas_list))
            entity_info = sorted(entity_info, key=lambda x: x[1][0])
            if entity_info:
                entity_substr_list, entity_offsets_list, entity_tags_list, entity_probas_list = zip(*entity_info)
                entity_substr_list = list(entity_substr_list)
                entity_offsets_list = list(entity_offsets_list)
                entity_tags_list = list(entity_tags_list)
                entity_probas_list = list(entity_probas_list)
            new_entity_substr_list = []
            new_entity_lemm_substr_list = []
            new_entity_offsets_list = []
            new_entity_init_offsets_list = []
            new_entity_tags_list = []
            new_entity_probas_list = []
            text = text.lower()
            text_from_sentences = " ".join(sentences_list)
            prev_init_end_offset = 0
            for entity_substr, (start_offset, end_offset), tag, proba in \
                    zip(entity_substr_list, entity_offsets_list, entity_tags_list, entity_probas_list):
                entity_substr_lower = entity_substr.lower()
                found_entity_substr = text_from_sentences[start_offset:end_offset]
                found_entity_substr = found_entity_substr.replace(".", " ").replace(")", " ").replace("(", " ").replace(
                    "  ", " ")
                new_text = text[prev_init_end_offset:]
                fnd_init = new_text.find(entity_substr_lower)
                corr_entity_substr = entity_substr
                for elem in replace_list:
                    entity_substr = entity_substr.replace(elem[0], elem[1])
                if fnd_init == -1:
                    fnd_init = new_text.find(entity_substr)
                if fnd_init == -1 and "-" in entity_substr:
                    fnd_init = new_text.find(entity_substr.replace("-", " - ").replace("  ", " "))
                    if fnd_init > -1:
                        corr_entity_substr = entity_substr.replace("-", " - ").replace("  ", " ")
                if fnd_init == -1 and ". " in entity_substr:
                    fnd_init = new_text.find(entity_substr.replace(". ", "."))
                    if fnd_init > -1:
                        corr_entity_substr = entity_substr.replace(". ", ".")
                if fnd_init == -1 and "/" in entity_substr:
                    fnd_init = new_text.find(entity_substr.replace(" / ", "/"))
                    if fnd_init > -1:
                        corr_entity_substr = entity_substr.replace(" / ", "/")
                if fnd_init == -1 and " " in entity_substr:
                    fnd_init = new_text.find(entity_substr.replace(" ", "  "))
                    if fnd_init > -1:
                        corr_entity_substr = entity_substr.replace(" ", "  ")
                if fnd_init == -1 and " " in entity_substr:
                    fnd_init = new_text.find(entity_substr.replace(" (", "("))
                    if fnd_init > -1:
                        corr_entity_substr = entity_substr.replace(" (", "(")
                if fnd_init == -1 and " ’" in entity_substr:
                    fnd_init = new_text.find(entity_substr.replace(" ’", "’"))
                    if fnd_init > -1:
                        corr_entity_substr = entity_substr.replace(" ’", "’")
                san_found_entity_substr = ''.join(
                    [ch for ch in found_entity_substr.lower() if (ch not in punctuation and ch != " ")])
                san_entity_substr = ''.join(
                    [ch for ch in entity_substr.lower() if (ch not in punctuation and ch != " ")])
                if san_entity_substr == san_found_entity_substr and fnd_init != -1 and entity_substr not in punctuation:
                    new_init_start_offset = prev_init_end_offset + fnd_init
                    new_init_end_offset = new_init_start_offset + len(corr_entity_substr)
                    for elem in delete_list:
                        entity_substr = entity_substr.replace(elem[0], elem[1])
                    if self.lemmatize:
                        entity_substr_tokens = entity_substr.split()
                        entity_substr_tokens = [self.morph.parse(tok)[0].normal_form for tok in entity_substr_tokens]
                        lemm_entity_substr = detokenize(entity_substr_tokens)
                    else:
                        lemm_entity_substr = entity_substr
                    new_entity_substr_list.append(entity_substr.replace("  ", " "))
                    new_entity_lemm_substr_list.append(lemm_entity_substr.replace("  ", " "))
                    new_entity_offsets_list.append([start_offset, end_offset])
                    new_entity_tags_list.append(tag)
                    new_entity_probas_list.append(proba)
                    new_entity_init_offsets_list.append([new_init_start_offset, new_init_end_offset])
                    prev_init_end_offset = new_init_end_offset

            new_entity_substr_batch.append(new_entity_substr_list)
            new_entity_lemm_substr_batch.append(new_entity_lemm_substr_list)
            new_entity_offsets_batch.append(new_entity_offsets_list)
            new_entity_tags_batch.append(new_entity_tags_list)
            new_entity_probas_batch.append(new_entity_probas_list)
            new_entity_init_offsets_batch.append(new_entity_init_offsets_list)

        return new_entity_substr_batch, new_entity_lemm_substr_batch, new_entity_offsets_batch, new_entity_init_offsets_batch, \
               new_entity_tags_batch, new_entity_probas_batch
