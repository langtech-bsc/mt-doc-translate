import gradio as gr
import os
import torch
import shutil

from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
from src.salamandraTA7b_translator import SalamandraTA7bTranslator, LANG_TO_ISO



temp_folder = 'tmp'
os.makedirs(temp_folder, exist_ok=True)

available_languages = sorted(list(LANG_TO_ISO.keys()))
    
allowed_extensions = ["docx","odt","csv","xlsx","txt","pptx","html","json"]

         
def process_file(filepath, source_lang, target_lang):
    # checking supported file types
    if filepath.split('.')[-1].lower() not in allowed_extensions:
        raise gr.Error(f"File format NOT supported. Supported files: {allowed_extensions}", duration=15)

    yield [gr.update(value="Processing...", visible=True),
           gr.update(visible=False)]
    
    model_path = "BSC-LT/salamandraTA-7b-instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        device_map="auto",
        dtype=torch.bfloat16
        ).eval() 

    translator = SalamandraTA7bTranslator(model, tokenizer)

    for status, translated_file_name in translator.translate_document(filepath, source_lang, target_lang):
        if translated_file_name: # finished
            abs_translated_path = os.path.abspath(translated_file_name)
            print("Finished file:", abs_translated_path)
            yield [gr.update(value="", visible=False), abs_translated_path]
            break
        else:
            yield [gr.update(value=status, visible=True), None]


def disable_button():
    return gr.update(interactive=False)


def enable_buttons_after_translation(file_path):
    print("file_path:", file_path)   
    if not file_path or not isinstance(file_path, str) or not os.path.exists(file_path):
        raise gr.Error("The translated file could not be prepared for download. Please try again.")
    return (
        gr.update(interactive=True),
        gr.update(label=f"Download {os.path.basename(file_path)}", value=file_path, visible=True)
    )


def update_other_dropdown(chosen_value, other_current_value):
    global available_languages
    # If user clears the dropdown, restore full choices to the other one
    if not chosen_value:
        return gr.update(choices=available_languages)
    # Remove the chosen language from the other dropdown
    new_choices = [lang for lang in available_languages if lang != chosen_value]
    # If the other dropdown currently holds an invalid language, clear it
    if other_current_value == chosen_value:
        return gr.update(choices=new_choices, value=None)
    # Otherwise keep the user's current selection
    return gr.update(choices=new_choices)


def check_ready_to_process(d1, d2, file):
    # Button is enabled only if ALL fields are non-empty / non-None
    ready = bool(d1 and d2 and file)
    return gr.update(interactive=ready)


DESCR = """
<div class="translator-header">

  <div class="translator-title">
    <span class="translator-icon">🌍</span>
    <div>
      <h1>Document Translator</h1>
      <p>Translate documents while preserving their original design</p>
    </div>
  </div>

  <div class="translator-language">
    <span class="language-label">ENGLISH</span>
    <p>
      Upload a supported document and receive a translated version
      while preserving its original formatting, layout and style.
    </p>
  </div>

  <div class="translator-formats">
    <span>DOCX</span>
    <span>ODT</span>
    <span>PPTX</span>
    <span>HTML</span>
    <span>+ more</span>
  </div>

  <p class="translator-note">
    PDF files are currently not supported.
  </p>

  <div class="translator-divider"></div>

  <div class="translator-language">
    <span class="language-label">CATALÀ</span>
    <p>
      Puja un document compatible i rebràs una versió traduïda
      que conservarà el format, la disposició i l'estil originals.
    </p>
  </div>

  <div class="translator-formats">
    <span>DOCX</span>
    <span>ODT</span>
    <span>PPTX</span>
    <span>HTML</span>
    <span>+ més</span>
  </div>

  <p class="translator-note">
    Actualment, els fitxers PDF no són compatibles.
  </p>

</div>
""".strip()

CSS = """
.translator-description-box {
    border: 1px solid var(--border-color-primary);
    border-radius: 16px;
    padding: 24px !important;
    margin-bottom: 20px;
}

.translator-header {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.translator-title {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 8px;
}

.translator-icon {
    font-size: 36px;
}

.translator-title h1 {
    font-size: 28px;
    margin: 0;
    font-weight: 700;
}

.translator-title p {
    margin: 4px 0 0;
    opacity: 0.7;
    font-size: 14px;
}

.translator-language p {
    font-size: 14px;
    line-height: 1.6;
    margin: 6px 0;
}

.language-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    opacity: 0.6;
}

.translator-formats {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.translator-formats span {
    border: 1px solid var(--border-color-primary);
    border-radius: 6px;
    padding: 5px 11px;
    font-size: 11px;
    font-weight: 600;
}

.translator-note {
    font-size: 11px;
    opacity: 0.6;
    margin: 0;
}

.translator-divider {
    height: 1px;
    background: var(--border-color-primary);
    margin: 12px 0;
}
"""

theme = gr.themes.Base(
    font=[gr.themes.GoogleFont('Libre Franklin'), gr.themes.GoogleFont('Public Sans'), 'system-ui', 'sans-serif'],
)

with gr.Blocks(theme=theme, css=CSS) as demo:
    gr.Markdown(DESCR, elem_classes="markdown-text")
    with gr.Row():
        dropdown1 = gr.Dropdown(label="Source language", choices=available_languages, value=None, interactive=True)
        dropdown2 = gr.Dropdown(label="Target language", choices=available_languages, value=None, interactive=True)
    with gr.Row():
        file_input = gr.File(label="Select file")
        d = gr.DownloadButton(visible=False)
    status_text = gr.Textbox(label="Status", visible=True)
    process_btn = gr.Button("Process", interactive=False)

    file_state = gr.State()

    process_btn.click(
        fn=disable_button,
        inputs=None,
        outputs=process_btn,
        queue=False
    ).then(
        fn=process_file,
        inputs=[file_input, dropdown1, dropdown2],
        outputs=[status_text, file_state]
    ).then(
        fn=enable_buttons_after_translation,
        inputs=[file_state],
        outputs=[process_btn, d],
        queue=False
    )

    dropdown1.change(
        fn=update_other_dropdown,
        inputs=[dropdown1, dropdown2],
        outputs=dropdown2
    )

    dropdown2.change(
        fn=update_other_dropdown,
        inputs=[dropdown2, dropdown1],
        outputs=dropdown1
    )
    
    # Whenever any input changes, run check_ready()
    inputs = [dropdown1, dropdown2, file_input]
    for inp in inputs:
        inp.change(
            fn=check_ready_to_process,
            inputs=inputs,
            outputs=[process_btn]
        )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0", 
        server_port=7860,
        allowed_paths=[temp_folder]
    )
