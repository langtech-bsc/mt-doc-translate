import re
import os
import spacy
import shutil

from tqdm import tqdm
from datetime import datetime

from src.utils import (file_to_moses, moses_to_file)



LANG_TO_ISO = {
    'Aragonese':'arg', 
    'Asturian':'ast', 
    'Basque':'eu', 
    'Bulgarian':'bg', 
    'Catalan':'ca', 
    'Catalan_Valencian':'vl', 
    'Croatian':'hr', 
    'Czech':'cs', 
    'Danish':'da', 
    'Dutch':'nl', 
    'English':'en', 
    'Estonian':'et',
    'Finnish':'fi', 
    'French':'fr', 
    'Galician':'gl', 
    'German':'de', 
    'Greek':'el', 
    'Hungarian':'hu', 
    'Irish':'ga', 
    'Italian':'it', 
    'Latvian':'lv', 
    'Lithuanian':'lt', 
    'Maltese':'mt', 
    'Norwegian Bokmål':'nb',
    'Norwegian Nynorsk':'nn', 
    'Occitan':'oc', 
    'Aranese':'arn', 
    'Polish':'pl', 
    'Portuguese':'pt', 
    'Romanian':'ro', 
    'Russian':'ru', 
    'Serbian_Cyrillic':'sr', 
    'Slovak':'sk', 
    'Slovenian':'sl', 
    'Spanish':'es', 
    'Swedish':'sv', 
    'Ukrainian':'uk', 
    'Welsh':'cy', 
    'Korean':'ko', 
    'Hindi':'hi', 
    'Chinese':'zh', 
    'Japanese':'ja', 
    'Arabic':'ar'
}


def lines_to_moses(lines, out_file_path):
    with open(out_file_path, "w") as out_file:
        for line in lines:
            out_file.write(line.strip() + "\n")


class SalamandraTA7bTranslator():

    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
        self.spacy_nlp = spacy.load("xx_ent_wiki_sm")
        self.spacy_nlp.add_pipe('sentencizer')
        
    def translate_text_by_sentences(self, lines, source_lang, target_lang): 
                 
        prompt_template = lambda \
            x: (f"Translate this {source_lang} text into {target_lang}. Preserve any formatting, tags, delimiters, "
                f"or structural elements exactly, and translate only the human-readable parts: {x}")

        total_translated = []
        yield "Translating...", None
        for i, text in tqdm(enumerate(lines), desc='Translating...'):
            translated_paragraphs = []

            # <lb/> is a tag indicating a line break, we want to split according to that to get the paragraphs
            for paragraph in text.split("<lb/>"):
                # print("Paragraph to translate:")
                # print(paragraph)
                # empty paragraph, we want to keep it to avoid problems when reconstructing the document
                if not paragraph.strip():
                    translated_paragraphs.append(paragraph)
                    continue
                sentences_in_paragraph = list(self.spacy_nlp(paragraph).sents)
                translated_sentences_in_paragraph = self.translate_sentences(sentences_in_paragraph, prompt_template)
                # join the sentences within the paragraph
                translated_paragraphs.append(" ".join(translated_sentences_in_paragraph))

            # rejoin the paragraphs using the line break tag
            total_translated.append("<lb/>".join(translated_paragraphs))

            percent_complete = int(((i + 1) / len(lines)) * 100)
            yield f"Translating {percent_complete}%...", None
        yield "", total_translated

    def translate_document(self, input_file, source_lang, target_lang, 
                           temp_folder: str = "tmp", tikal_folder: str = "okapi-apps_gtk2-linux-x86_64_1.47.0"): 
        """
        Extracts text from file and sends it to translate_text_by_sentences
        """
        input_filename = input_file.split("/")[-1]
        os.makedirs(temp_folder, exist_ok=True)

        # copy the original file to the temporal folder to avoid common issues with tikal
        temp_input_file = os.path.join(temp_folder, input_filename)
        shutil.copy(input_file, temp_input_file)
        print(f"Copied {input_file} to {temp_input_file}")

        original_xliff_file = os.path.join(temp_folder, input_filename + ".xlf")
        plain_text_file = file_to_moses(temp_input_file, LANG_TO_ISO[source_lang], LANG_TO_ISO[target_lang], 
                                        tikal_folder, original_xliff_file)

        lines = open(plain_text_file, "r", encoding="utf-8").read().splitlines()

        for status, translated_lines in self.translate_text_by_sentences(lines, source_lang, target_lang):
            yield status, None

        # create moses file with translated lines
        translated_moses_file = os.path.join(original_xliff_file + f".{LANG_TO_ISO[target_lang]}")
        lines_to_moses(translated_lines, translated_moses_file)

        # recreate the document with the translations
        translated_file_path = moses_to_file(translated_moses_file, LANG_TO_ISO[source_lang], LANG_TO_ISO[target_lang], 
                                             tikal_folder, original_xliff_file)

        print(f"Saved file in {translated_file_path}")
        yield "", translated_file_path

    def translate_sentences(self, sentences, prompt_template):
        translated_sentences_in_paragraph = []
        for sentence in sentences:
            input_sentence = sentence.text
            # input_sentence = sentence.text_with_ws if sentence.text.endswith(".") else sentence.text
            # skip translating sentences made up of only numbers and symbols. Note: emojis and non-english chars are not skipped 
            if re.fullmatch(r"""^[0-9\s!"#$%&\'()*+,\-./:;<=>?@\[\\\]^_`{|}~]+$""", input_sentence):
                print(f'{input_sentence} PS: NOT TRANSLATED')
                translated_sentences_in_paragraph.append(input_sentence)
                continue
            message = [{"role": "user", "content": prompt_template(input_sentence)}]
            date_string = datetime.today().strftime('%Y-%m-%d')
            print(message)
            prompt = self.tokenizer.apply_chat_template(
                message,
                tokenize=False,
                add_generation_prompt=True,
                date_string=date_string
            )
            inputs = self.tokenizer(prompt, add_special_tokens=False, return_tensors="pt").to(self.model.device)
            input_length = inputs.input_ids.shape[1]
            outputs = self.model.generate(
                input_ids=inputs.input_ids,
                max_new_tokens=input_length * 2, 
                early_stopping=True,
                num_beams=1
            )
            translated_text = self.tokenizer.decode(outputs[0, input_length:], skip_special_tokens=True).strip()
            # fixing some tag formatting issue that causes tikal merge errors
            # adds a closing quote (") where missing in tags <g id="[0-9]"></g>
            translated_text = re.sub(r'<g id="(\d+)(?=>)', r'<g id="\1"', translated_text)
            # adds a closing slash to tags <x id="[0-9]"/> where missing
            translated_text = re.sub(r'<x(\s+id="\d+")\s*>',r'<x\1/>', translated_text)
            print(translated_text)
            translated_sentences_in_paragraph.append(translated_text)
        return translated_sentences_in_paragraph


