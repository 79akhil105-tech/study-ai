import gradio as gr
import os
from pathlib import Path
from src.config import settings
from src.parsers.pdf_parser import PDFParser
from src.parsers.docx_parser import DocxParser
from src.parsers.image_parser import ImageParser
from src.pipeline.chunker import chunk_text
from src.llm.engine import LLMEngine
from src.utils.helpers import logger

pdf_parser = PDFParser()
docx_parser = DocxParser()
img_parser = ImageParser()


def warmup_models():
    logger.info("Warming up text LLM...")
    try:
        LLMEngine.get_text_llm()
        logger.info("Text LLM ready.")
    except Exception as e:
        logger.critical(f"Model load failed: {e}")


def process_files(files, progress=gr.Progress(track_tqdm=True)):
    if not files:
        yield "No files uploaded.", "", "Error: No files provided."
        return

    temp_dir = Path(settings.app['temp_dir'])
    temp_dir.mkdir(exist_ok=True)
    parsed_docs = []
    all_images = []
    status_log = []

    progress(0.05, desc="Parsing Documents...")
    for f in files:
        fname = Path(f.name).name
        ext = Path(fname).suffix.lower()
        status_log.append(f"Parsing: {fname}")
        yield "", "", "\n".join(status_log)
        try:
            if ext == ".pdf":
                parsed = pdf_parser.parse(f.name)
            elif ext == ".docx":
                parsed = docx_parser.parse(f.name)
            elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                parsed = img_parser.parse(f.name)
            else:
                status_log.append(f"Skipped: {fname}")
                continue
            parsed_docs.append(parsed)
            all_images.extend(parsed.images)
            status_log.append(f"OK: {len(parsed.text)} chars, {len(parsed.images)} images")
        except Exception as e:
            status_log.append(f"FAILED: {fname} - {e}")

    if not parsed_docs:
        yield "No valid content extracted.", "", "\n".join(status_log)
        return

    # Vision analysis
    vision_reports = []
    if all_images and settings.processing.get('ocr_enabled', True):
        status_log.append(f"Analyzing {len(all_images)} images...")
        yield "", "", "\n".join(status_log)
        for i, img in enumerate(all_images):
            try:
                report = LLMEngine.analyze_image(img)
                vision_reports.append(f"## Image {i+1}\n{report}")
                status_log.append(f"Image {i+1} analyzed.")
            except Exception as e:
                status_log.append(f"Vision error {i+1}: {e}")
            yield "", "", "\n".join(status_log)

    if vision_reports:
        vision_text = "\n\n=== VISUAL CONTENT ===\n\n" + "\n\n".join(vision_reports)
        if parsed_docs:
            parsed_docs[0].text += vision_text
        else:
            from src.parsers.base import ParsedContent
            parsed_docs.append(ParsedContent(text=vision_text, images=[], metadata={}, source_name="vision"))

    # Map phase
    all_chunks = []
    for pc in parsed_docs:
        for ch in chunk_text(pc.text):
            all_chunks.append((ch, pc.source_name))

    status_log.append(f"Processing {len(all_chunks)} chunks...")
    chunk_summaries = []
    for i, (chunk, src) in enumerate(all_chunks):
        progress(0.1 + 0.5 * (i / len(all_chunks)), desc=f"Chunk {i+1}/{len(all_chunks)}")
        prompt = settings.prompts['map_summary'].format(text=chunk)
        summary = LLMEngine.generate_text(prompt, stream=False, max_tokens=1024)
        chunk_summaries.append(f"[{src}]\n{summary}")
        status_log.append(f"Chunk {i+1}/{len(all_chunks)} done.")
        yield "", "", "\n".join(status_log)

    combined = "\n\n---\n\n".join(chunk_summaries)
    final_prompt = settings.prompts['reduce_summary'].format(text=combined)

    # Stream final summary
    status_log.append("Generating final summary...")
    yield "", "", "\n".join(status_log)
    full_summary = ""
    for token in LLMEngine.generate_text(final_prompt, stream=True):
        full_summary += token
        yield full_summary, "", "\n".join(status_log)

    # Stream study guide
    status_log.append("Generating study guide...")
    guide_prompt = settings.prompts['study_guide'].format(text=full_summary)
    full_guide = ""
    for token in LLMEngine.generate_text(guide_prompt, stream=True, max_tokens=4096):
        full_guide += token
        yield full_summary, full_guide, "\n".join(status_log)

    status_log.append("Done!")
    yield full_summary, full_guide, "\n".join(status_log)


with gr.Blocks(title=settings.app['title'], theme=gr.themes.Soft()) as demo:
    gr.Markdown(f"# {settings.app['title']}\n**Fully Offline | Local LLMs | PDF/DOCX/Images | Study Guides**")
    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="Upload PDFs, DOCX, Images",
                file_count="multiple",
                file_types=[".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp"],
                height=200
            )
            btn = gr.Button("Analyze & Summarize", variant="primary", size="lg")
            status_box = gr.Textbox(label="Log", lines=10, interactive=False, autoscroll=True)
        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.TabItem("Detailed Summary"):
                    summary_out = gr.Markdown(show_copy_button=True)
                with gr.TabItem("Study Guide"):
                    guide_out = gr.Markdown(show_copy_button=True)
    btn.click(fn=process_files, inputs=[file_input], outputs=[summary_out, guide_out, status_box], queue=True)

if __name__ == "__main__":
    warmup_models()
    demo.queue(max_size=5).launch(server_name="0.0.0.0", server_port=7860, show_api=False)
