#!/usr/bin/env python3
"""
docx_to_qti.py

Teacher-friendly DOCX -> QTI converter.

- Usage:
    * No args: converts all .docx in script folder
    * Folder path arg: converts .docx in that folder
    * Single .docx path arg: converts that file

- Produces <filename>_qti.zip next to the .docx containing:
    imsmanifest.xml
    assessment.xml
    media/ (if images present)

- Auto-installs python-docx and lxml using: python -m pip install --user ...
- Writes docx_to_qti.log beside the script.
"""

from pathlib import Path
import sys, subprocess, importlib.util, site, importlib, os, re, zipfile, shutil, traceback, logging
from collections import namedtuple
from xml.etree import ElementTree as ET

# Logging
LOG_PATH = Path(__file__).with_suffix('.log')
logging.basicConfig(filename=str(LOG_PATH), level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s: %(message)s')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)
log = logging.getLogger(__name__).info
log_debug = logging.getLogger(__name__).debug
log_err = logging.getLogger(__name__).error

log("Starting docx_to_qti.py")

# Ensure user site-packages are visible
def ensure_user_site_on_path():
    try:
        user_site = site.getusersitepackages()
        if user_site and user_site not in sys.path:
            sys.path.insert(0, user_site)
            log_debug(f"Added user site to sys.path: {user_site}")
    except Exception:
        try:
            site.addusersitepackages()
        except Exception:
            pass

def ensure_package(pkg_name, import_name=None):
    import_name = import_name or pkg_name
    if importlib.util.find_spec(import_name) is None:
        log(f"[installer] Installing {pkg_name} (user)...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", pkg_name])
            ensure_user_site_on_path()
            importlib.invalidate_caches()
        except Exception as e:
            log_err(f"Failed to install {pkg_name}: {e}")
            raise

ensure_user_site_on_path()
for _pkg, _imp in [("python-docx", "docx"), ("lxml", None)]:
    try:
        ensure_package(_pkg, import_name=_imp)
    except Exception:
        print(f"Failed to auto-install {_pkg}. Please run: python -m pip install --user {_pkg}")
        sys.exit(1)

try:
    from docx import Document
except Exception as e:
    log_err(f"Cannot import python-docx: {e}")
    print("python-docx not available. Install with: python -m pip install --user python-docx")
    sys.exit(1)

# Data structure for parsed question
Question = namedtuple("Question", ["number", "prompt_html", "options_html", "correct_indices"])

# Helpers for parsing
def is_private_use_start(s: str):
    if not s: return False
    return 0xE000 <= ord(s[0]) <= 0xF8FF

def extract_images(doc, media_dir: Path):
    """Extract images from docx part relationships into media_dir. Return rId->filename map."""
    media_dir.mkdir(parents=True, exist_ok=True)
    rel_map = {}
    try:
        for rel in doc.part.rels.values():
            try:
                reltype = getattr(rel, "reltype", "")
                if "image" in reltype:
                    img_part = rel.target_part
                    img_name = Path(img_part.partname).name
                    dest = media_dir / img_name
                    with open(dest, "wb") as f:
                        f.write(img_part.blob)
                    # some rel objects use .rId attribute, others use .rId-like; we try both
                    rid = getattr(rel, "rId", None) or getattr(rel, "rid", None) or getattr(rel, "rId", None)
                    if not rid:
                        # fallback create a unique key
                        rid = f"r{len(rel_map)+1}"
                    rel_map[rid] = img_name
                    log_debug(f"Extracted image {img_name} (rid={rid})")
            except Exception as e:
                log_debug(f"image extraction error for rel: {e}")
    except Exception as e:
        log_err(f"Failed to iterate doc rels: {e}")
    return rel_map

def paragraph_to_html(paragraph, rel_map):
    parts = []
    for run in paragraph.runs:
        # detect embedded images (run._r.xml contains r:embed="rIdX")
        m = re.search(r'r:embed="(rId\d+)"', run._r.xml)
        if m:
            rId = m.group(1)
            img = rel_map.get(rId)
            if img:
                # url-encode filename
                img_url = re.sub(r'[^a-zA-Z0-9_.-]', lambda m: f'%{ord(m.group(0)):02x}', img)
                parts.append(f'<img src="{img_url}" alt="{img}" />')
                continue
        t = run.text or ""
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(t)
    return "".join(parts).strip()

def is_run_highlighted(run):
    """Safely checks if a run is highlighted, handling cases where highlight is 'none'."""
    try:
        # The property access itself can raise ValueError
        return run.font.highlight_color is not None
    except ValueError:
        # This occurs if the highlight color is 'none', which is not a valid WD_COLOR_INDEX
        return False

def parse_docx_questions(path: Path, media_dir: Path):
    log(f"Parsing DOCX: {path}")
    doc = Document(str(path))
    rel_map = extract_images(doc, media_dir)

    paras = doc.paragraphs
    questions = []
    i = 0
    qnum = 0
    while i < len(paras):
        p = paras[i]; text = p.text.strip()
        if re.match(r'^\s*Question\s+\d+', text, re.I):
            qnum += 1
            i += 1
            body = []
            while i < len(paras) and not re.match(r'^\s*Question\s+\d+', paras[i].text.strip(), re.I):
                body.append(paras[i]); i += 1
            # split prompt and option blocks
            prompt_parts = []
            option_blocks = []
            option_para_blocks = []
            current_block = None
            current_para_block = None
            reading_options = False
            for bp in body:
                t = bp.text
                if not reading_options:
                    # detect start of options by private marker or numbered/lettered prefixes or "Select"
                    if t and (is_private_use_start(t) or re.match(r'^[A-D]\.|^[A-D]\)|^[0-9]+\.', t.strip()) or re.search(r'Select (only|all|multiple)', t, re.I)):
                        reading_options = True
                    else:
                        prompt_parts.append(bp); continue
                # reading options: each non-empty paragraph is a new option block
                if t:
                    text_for_block = t
                    if is_private_use_start(t):
                        # The private use character is a highlight marker; remove it from option text
                        text_for_block = t.lstrip(chr(ord(t[0]))) if t else t

                    option_blocks.append([text_for_block.strip()])
                    option_para_blocks.append([bp])

            # Clean "Select..." from the first option block if it exists
            if option_blocks:
                first_block_text = option_blocks[0][0]
                cleaned_text = re.sub(r'^\s*Select (only one|all that apply|only|all|multiple|one)\s*', '', first_block_text, flags=re.I).strip()
                if cleaned_text:
                    option_blocks[0][0] = cleaned_text
                else:
                    # The block was *only* "Select...", so remove it entirely
                    option_blocks.pop(0)
                    option_para_blocks.pop(0)

            options = ["\n".join([x for x in block if x is not None]).strip() for block in option_blocks]
            # determine correct indices from highlighted runs in paragraphs
            correct_indices = []
            for idx, para_block in enumerate(option_para_blocks):
                found = any(is_run_highlighted(run) for p in para_block for run in p.runs)
                if found:
                    correct_indices.append(idx)
            prompt_html = " ".join([paragraph_to_html(pp, rel_map) for pp in prompt_parts])
            options_html = [o for o in options]
            questions.append(Question(qnum, prompt_html, options_html, correct_indices))
        else:
            i += 1

    # fallback parsing when no Question headers found
    if not questions:
        log("No questions detected by headers; attempting fallback by 'Select' markers")
        i = 0; qnum = 0
        while i < len(paras):
            p = paras[i]; text = p.text.strip()
            if re.search(r'Select (only one|all that apply|only|one|multiple)', text, re.I):
                # gather prompt (backwards)
                start = i-1
                prompt_parts = []
                while start >= 0 and not re.match(r'^\s*Question\s+\d+', paras[start].text.strip(), re.I):
                    prompt_parts.insert(0, paras[start]); start -= 1
                # gather options forwards
                opts = []
                j = i+1
                while j < len(paras) and paras[j].text.strip():
                    opts.append(paras[j].text.strip()); j += 1
                qnum += 1
                prompt_html = " ".join([paragraph_to_html(pp, {}) for pp in prompt_parts])
                questions.append(Question(qnum, prompt_html, opts, []))
                i = j
            else:
                i += 1

    log(f"Detected {len(questions)} questions")
    return questions, rel_map

# QTI builders
NS = "http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace('', NS)
ET.register_namespace('xsi', XSI)

def make_item_element(q: Question):
    item = ET.Element('item', {'ident': f'ITEM_{q.number}', 'title': f'Question {q.number}'})
    # itemmetadata
    itemmeta = ET.SubElement(item, 'itemmetadata')
    qtim = ET.SubElement(itemmeta, 'qtimetadata')
    md = ET.SubElement(qtim, 'qtimetadatafield')
    ET.SubElement(md, 'fieldlabel').text = 'question_type'
    ET.SubElement(md, 'fieldentry').text = ('multiple_answer_question' if len(q.correct_indices)>1 else 'multiple_choice_question')
    # presentation
    pres = ET.SubElement(item, 'presentation')
    mat = ET.SubElement(pres, 'material')
    mt = ET.SubElement(mat, 'mattext', {'texttype': 'text/html'})
    mt.text = q.prompt_html or ''
    respid = f'RESP_{q.number}'
    resp = ET.SubElement(pres, 'response_lid', {'ident': respid, 'rcardinality': ('Multiple' if len(q.correct_indices)>1 else 'Single')})
    render = ET.SubElement(resp, 'render_choice')
    for idx, opt_html in enumerate(q.options_html):
        choice_ident = f'CHOICE_{q.number}_{idx+1}'
        label = ET.SubElement(render, 'response_label', {'ident': choice_ident})
        matc = ET.SubElement(label, 'material')
        ET.SubElement(matc, 'mattext', {'texttype': 'text/plain'}).text = opt_html or ''
    # resprocessing
    resproc = ET.SubElement(item, 'resprocessing')
    outcomes = ET.SubElement(resproc, 'outcomes')
    ET.SubElement(outcomes, 'decvar', {'maxvalue':'100', 'minvalue':'0', 'varname':'SCORE', 'vartype':'Decimal'})
    if q.correct_indices:
        # success condition
        rc = ET.SubElement(resproc, 'respcondition', {'title':'correct'})
        cond = ET.SubElement(rc, 'conditionvar')
        if len(q.correct_indices) > 1:
            # multiple response: all correct are chosen AND all incorrect are NOT chosen
            andel = ET.SubElement(cond, 'and')
            for i in range(len(q.options_html)):
                choice_id = f'CHOICE_{q.number}_{i+1}'
                if i in q.correct_indices:
                    ve = ET.SubElement(andel, 'varequal', {'respident': respid})
                    ve.text = choice_id
                else:
                    notel = ET.SubElement(andel, 'not')
                    ve = ET.SubElement(notel, 'varequal', {'respident': respid})
                    ve.text = choice_id
        else:
            # single correct answer
            ve = ET.SubElement(cond, 'varequal', {'respident': respid})
            ve.text = f'CHOICE_{q.number}_{q.correct_indices[0]+1}'
        ET.SubElement(rc, 'setvar', {'action':'Set', 'varname': 'SCORE'}).text = '100'
        # failure condition
        rc2 = ET.SubElement(resproc, 'respcondition', {'title':'incorrect'})
        cond2 = ET.SubElement(rc2, 'conditionvar')
        ET.SubElement(cond2, 'other')
        ET.SubElement(rc2, 'setvar', {'action':'Set', 'varname': 'SCORE'}).text = '0'
    else: # no correct answers specified
        rc = ET.SubElement(resproc, 'respcondition', {'title':'unscored'})
        cond = ET.SubElement(rc, 'conditionvar')
        ET.SubElement(cond, 'other')
        ET.SubElement(rc, 'setvar', {'action':'Set', 'varname': 'SCORE'}).text = '0'
    return item

def build_assessment_xml(questions):
    root = ET.Element('questestinterop', {'xmlns': NS, 'xmlns:xsi': XSI, 'xsi:schemaLocation': f'{NS} {NS}p1.xsd'})
    assess = ET.SubElement(root, 'assessment', {'ident':'ASMT1', 'title':'Imported Assessment'})
    qtim = ET.SubElement(assess, 'qtimetadata')
    mdfield = ET.SubElement(qtim, 'qtimetadatafield')
    ET.SubElement(mdfield, 'fieldlabel').text = 'cc_maxattempts'
    ET.SubElement(mdfield, 'fieldentry').text = '1'
    section = ET.SubElement(assess, 'section', {'ident':'root_section'})
    for q in questions:
        section.append(make_item_element(q))
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)

def build_manifest(rel_map):
    root = ET.Element('manifest', {'identifier':'MANIFEST_1'})
    md = ET.SubElement(root, 'metadata')
    ET.SubElement(md, 'schema').text = 'IMS QTI'
    ET.SubElement(md, 'schemaversion').text = '1.2'
    ET.SubElement(root, 'organizations')
    resources = ET.SubElement(root, 'resources')
    # assessment resource
    r = ET.SubElement(resources, 'resource', {'identifier':'RES_ASMT1', 'type':'imsqti_xmlv1p2', 'href':'assessment.xml'})
    ET.SubElement(r, 'file', {'href':'assessment.xml'})
    # image resources
    for rid, fname in rel_map.items():
        encoded_fname = re.sub(r'[^a-zA-Z0-9_.-]', lambda m: f'%{ord(m.group(0)):02x}', fname)
        r_img = ET.SubElement(resources, 'resource', {'identifier': rid, 'type': 'imsgraphic', 'href': encoded_fname})
        ET.SubElement(r_img, 'file', {'href': f'media/{fname}'})
        ET.SubElement(r, 'dependency', {'identifierref': rid})
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)

def convert_docx_to_qti_zip(input_docx: Path, output_zip: Path):
    # Use a temporary directory for all intermediate files
    tmp_root = Path(input_docx).with_suffix(f'.tmp_{os.getpid()}')
    if tmp_root.exists():
        try: shutil.rmtree(tmp_root)
        except: pass
    tmp_root.mkdir(parents=True, exist_ok=True)

    try:
        # Define media directory inside the temp root
        media_dir = tmp_root / 'media'
        media_dir.mkdir()

        # Parse questions and extract images into the media directory
        questions, rel_map = parse_docx_questions(input_docx, media_dir)
        log_debug(f"Questions parsed: {len(questions)}")

        # Build XML files
        assessment_bytes = build_assessment_xml(questions)
        manifest_bytes = build_manifest(rel_map)

        # Write XML files to the temp root
        (tmp_root / 'assessment.xml').write_bytes(assessment_bytes)
        (tmp_root / 'imsmanifest.xml').write_bytes(manifest_bytes)

        # Create the zip archive
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            # Add manifest and assessment XML
            z.write(tmp_root / 'imsmanifest.xml', arcname='imsmanifest.xml')
            z.write(tmp_root / 'assessment.xml', arcname='assessment.xml')

            # Add media files if any were extracted
            if media_dir.exists() and any(media_dir.iterdir()):
                for p in media_dir.iterdir():
                    z.write(p, arcname=f'media/{p.name}')

        log(f"Created zip: {output_zip}")
        return True
    except Exception as e:
        log_err(f"Error converting {input_docx}: {e}")
        traceback.print_exc()
        return False
    finally:
        # Clean up the temporary directory
        if tmp_root.exists():
            try: shutil.rmtree(tmp_root)
            except Exception as e:
                log_err(f"Failed to clean up temp dir {tmp_root}: {e}")

# Batch helpers
def batch_process_folder(folder: Path):
    docx_files = sorted(folder.glob("*.docx"))
    if not docx_files:
        log("No .docx files found in folder")
        return 0
    success = 0
    for d in docx_files:
        out = d.with_name(d.stem + "_qti.zip")
        if convert_docx_to_qti_zip(d, out):
            log(f"[OK] Created {out.name}"); success += 1
        else:
            log_err(f"[FAIL] {d.name}")
    return success

def batch_process_single_file(file_path: Path):
    if not file_path.exists() or file_path.suffix.lower() != ".docx":
        log_err(f"Invalid .docx file: {file_path}"); return 0
    out = file_path.with_name(file_path.stem + "_qti.zip")
    if convert_docx_to_qti_zip(file_path, out):
        log(f"[OK] Created {out.name}"); return 1
    else:
        log_err(f"[FAIL] {file_path.name}"); return 0

def main():
    try:
        if len(sys.argv) <= 1:
            folder = Path(__file__).parent
            n = batch_process_folder(folder)
        else:
            arg = Path(sys.argv[1])
            if arg.is_file() and arg.suffix.lower() == ".docx":
                n = batch_process_single_file(arg)
            elif arg.is_dir():
                n = batch_process_folder(arg)
            else:
                folder = Path(__file__).parent
                n = batch_process_folder(folder)
        if n > 0:
            log(f"Done. Created {n} _qti.zip file(s).")
            sys.exit(0)
        else:
            log("No files created.")
            sys.exit(1)
    except Exception as e:
        log_err(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
