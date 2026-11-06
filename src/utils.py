import os
import re
import glob
import unicodedata

from spacy.tokens import Doc
from subprocess import Popen, PIPE
from itertools import groupby



def moses_to_file(translated_moses_file: str, source_lang: str, target_lang: str, tikal_folder: str,
                      original_xliff_file_path: str):
    # prints moses file for debug
    # with open(translated_moses_file, "r", encoding="utf-8") as file:
    #     print("\nTRANSLATED MOSES FILE:\n")
    #     for line in file:
    #         print(line)

    # put the translations into the xlf
    tikal_moses_to_xliff_command = [os.path.join(tikal_folder, "tikal.sh"), "-lm", original_xliff_file_path, "-sl",
                                    source_lang, "-tl", target_lang, "-from", translated_moses_file, "-totrg",
                                    "-noalttrans", "-to", original_xliff_file_path]
    Popen(tikal_moses_to_xliff_command).wait()

    # any tags that are still <g> have not been paired between original and translated texts by tikal so we remove
    # them. This may happen if a word in the original language has been split in more that one words that have other
    # words in between, or an error in fastalign
    result = open(original_xliff_file_path).read()
    result = re.sub(r'<g id="\d+">(.*?)</g>', r'\1', result)
    # fixing some tag formatting issue that causes tikal merge errors
    # adds a closing quote (") where missing in tags <g id="[0-9]"></g>
    result = re.sub(r'<g id="(\d+)(?=>)', r'<g id="\1"', result)
    # adds a closing slash to tags <x id="[0-9]"/> where missing
    result = re.sub(r'<x(\s+id="\d+")\s*>',r'<x\1/>', result)
    # remove all <x .../> tags where id is 6 or greater (even if other attributes exist)
    result = re.sub(r"""<x\b[^>]*\bid=["\'](?:[6-9]|[1-9]\d+)["\'][^>]*/>""", '', result)
    open(original_xliff_file_path, "w").write(result)

    # merge into a docx again
    tikal_merge_doc_command = [os.path.join(tikal_folder, "tikal.sh"), "-m", original_xliff_file_path]
    final_process = Popen(tikal_merge_doc_command, stdout=PIPE, stderr=PIPE)
    stdout, stderr = final_process.communicate()
    final_process.wait()

    stdout_text = stdout.decode('utf-8', errors='ignore')
    stderr_text = stderr.decode('utf-8', errors='ignore')

    # If it failed, print BOTH stdout and stderr along with the exit code, and fail xliff for debug
    if final_process.returncode != 0:
        raise RuntimeError(
            f"\nTikal merge failed with exit code: {final_process.returncode}\n"
            f"\nFAILED xliff:\n{result}\n" # prints full failed .xlf that couldn't merge for debug
            f"=== STDOUT ===\n{stdout_text}\n"
            f"=== STDERR ===\n{stderr_text}\n"
        )

    # get the path to the output file
    return re.search(r'(?<=Output:\s)(.*)', stdout_text)[0]


def file_to_moses(input_file: str, source_lang: str, target_lang: str, tikal_folder: str,
                      original_xliff_file_path: str) -> str:
    """
    Given a document, this function generates an xliff file and then a plain text file with the text contents
    while keeping style and formatting using tags like <g id=1> </g>

    Parameters:
    input_file: Path to document to process
    source_lang: Source language of the document
    target_lang: Target language of the document
    tikal_folder: Folder where tikal.sh is located
    original_xliff_file_path: Path to xliff file to generate, which will be use later

    Returns:
    string: Path to plain text file
    """

    tikal_xliff_command = [os.path.join(tikal_folder, "tikal.sh"), "-x", input_file, "-nocopy", "-sl", source_lang,
                           "-tl", target_lang]
    Popen(tikal_xliff_command).wait()

    tikal_moses_command = [os.path.join(tikal_folder, "tikal.sh"), "-xm", original_xliff_file_path, "-sl", source_lang,
                           "-tl", target_lang]
    Popen(tikal_moses_command).wait()

    return os.path.join(original_xliff_file_path + f".{source_lang}")
