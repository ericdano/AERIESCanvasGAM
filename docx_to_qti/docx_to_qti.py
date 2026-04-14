#!/usr/bin/env python3
import os, re, uuid, zipfile, csv, io
from pathlib import Path
from collections import namedtuple
from xml.etree import ElementTree as ET
from docx import Document
from docx.enum.text import WD_COLOR_INDEX

Question = namedtuple("Question", ["number", "type", "prompt", "options", "corrects"])

def parse_docx(file_path):
    doc = Document(str(file_path))
    full_content = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text: continue
        is_highlighted = any(run.font.highlight_color == WD_COLOR_INDEX.YELLOW for run in p.runs)
        full_content.append(f"* {text}" if is_highlighted and not text.startswith('*') else text)
    return parse_text_based("\n".join(full_content))

def parse_text_based(content):
    blocks = re.split(r'Title:', content, flags=re.I)
    questions = []
    for idx, block in enumerate(blocks[1:], 1):
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue

        header = lines[0].lower()
        q_type = "multiple_choice_question"
        if "multiple answer" in header: q_type = "multiple_answers_question"
        elif "true or false" in header: q_type = "true_false_question"
        elif "matching" in header: q_type = "matching_question"
        elif "fill-in-the-blank" in header: q_type = "fill_in_multiple_blanks_question"
        elif "numeric" in header: q_type = "numerical_question"
        elif "formula" in header: q_type = "essay_question" # Maps to essay for preview safety
        elif "essay" in header: q_type = "essay_question"
        elif "file upload" in header: q_type = "file_upload_question"

        prompt, options, corrects = "", [], []
        for line in lines[1:]:
            if line.lower().startswith('points:'): continue
            if line.startswith('*') or line.startswith('[x]'):
                options.append(re.sub(r'^(\*|\[x\])\s*([a-z]\)\s*)?', '', line, flags=re.I).strip())
                corrects.append(len(options) - 1)
            elif re.match(r'^[a-z]\)\s+', line, re.I) or line.startswith('[ ]'):
                options.append(re.sub(r'^([a-z]\)\s*|\[\s\]\s*)', '', line, flags=re.I).strip())
            elif "->" in line: options.append(line)
            elif line.lower().startswith('[answer]') or line.lower().startswith('[formula]'):
                val = line.replace('[answer]', '').replace('[formula]', '').strip()
                options.append(val); corrects.append(len(options)-1)
            elif not options: prompt += " " + line

        questions.append(Question(idx, q_type, prompt.strip(), options, corrects))
    return questions

def build_qti_package(questions, output_zip, title):
    root = ET.Element('questestinterop', {'xmlns': "http://www.imsglobal.org/xsd/ims_qtiasiv1p2"})
    assess = ET.SubElement(root, 'assessment', {'ident': f"ASMT_{uuid.uuid4().hex[:8]}", 'title': title})
    section = ET.SubElement(assess, 'section', {'ident': 'root_section'})

    for q in questions:
        item = ET.SubElement(section, 'item', {'ident': f"g{uuid.uuid4().hex[:12]}", 'title': f"Q{q.number}"})
        item_meta = ET.SubElement(item, 'itemmetadata')
        qti_meta = ET.SubElement(item_meta, 'qtimetadata')

        f1 = ET.SubElement(qti_meta, 'qtimetadatafield')
        ET.SubElement(f1, 'fieldlabel').text = 'question_type'
        ET.SubElement(f1, 'fieldentry').text = q.type

        f2 = ET.SubElement(qti_meta, 'qtimetadatafield')
        ET.SubElement(f2, 'fieldlabel').text = 'points_possible'
        ET.SubElement(f2, 'fieldentry').text = '1'

        pres = ET.SubElement(item, 'presentation')
        ET.SubElement(ET.SubElement(pres, 'material'), 'mattext', {'texttype': 'text/html'}).text = q.prompt

        resproc = ET.SubElement(item, 'resprocessing')
        outcomes = ET.SubElement(resproc, 'outcomes')
        ET.SubElement(outcomes, 'decvar', {'maxvalue': '100', 'minvalue': '0', 'varname': 'SCORE', 'vartype': 'Decimal'})

        if q.type in ["essay_question", "file_upload_question"]:
            res_str = ET.SubElement(pres, 'response_str', {'ident': 'response1', 'rcardinality': 'Single'})
            ET.SubElement(res_str, 'render_fib')

        elif q.type == "numerical_question":
            res_str = ET.SubElement(pres, 'response_str', {'ident': 'response1', 'rcardinality': 'Single'})
            ET.SubElement(res_str, 'render_fib', {'fibtype': 'Decimal'})
            if q.corrects:
                cond = ET.SubElement(resproc, 'respcondition', {'continue': 'No'})
                cvar = ET.SubElement(cond, 'conditionvar')
                ET.SubElement(cvar, 'varequal', {'respident': 'response1'}).text = str(q.options[q.corrects[0]])
                ET.SubElement(cond, 'setvar', {'action': 'Set', 'varname': 'SCORE'}).text = '100'

        elif q.type == "matching_question":
            pairs = [opt.split('->', 1) for opt in q.options if "->" in opt]
            for i, (l, r) in enumerate(pairs):
                rlid = ET.SubElement(pres, 'response_lid', {'ident': f'response_{i}'})
                ET.SubElement(ET.SubElement(rlid, 'material'), 'mattext').text = l.strip()
                rc_render = ET.SubElement(rlid, 'render_choice')
                for j, (_, rv) in enumerate(pairs):
                    lab = ET.SubElement(rc_render, 'response_label', {'ident': f'ID_{j}'})
                    ET.SubElement(ET.SubElement(lab, 'material'), 'mattext').text = rv.strip()

                cond = ET.SubElement(resproc, 'respcondition')
                ET.SubElement(ET.SubElement(cond, 'conditionvar'), 'varequal', {'respident': f'response_{i}'}).text = f'ID_{i}'
                ET.SubElement(cond, 'setvar', {'action': 'Add', 'varname': 'SCORE'}).text = str(round(100/len(pairs), 2))

        elif q.type == "fill_in_multiple_blanks_question":
            blanks = re.findall(r'\[(.*?)\]', q.prompt)
            for i, b_name in enumerate(blanks):
                ET.SubElement(pres, 'response_lid', {'ident': f'response_{b_name}'})
                cond = ET.SubElement(resproc, 'respcondition')
                ET.SubElement(ET.SubElement(cond, 'conditionvar'), 'varequal', {'respident': f'response_{b_name}'}).text = b_name
                ET.SubElement(cond, 'setvar', {'action': 'Add', 'varname': 'SCORE'}).text = str(round(100/len(blanks), 2))

        else: # MC, TF, Multiple Answer
            res_lid = ET.SubElement(pres, 'response_lid', {'ident': 'response1', 'rcardinality': 'Multiple' if q.type == "multiple_answers_question" else 'Single'})
            render = ET.SubElement(res_lid, 'render_choice')
            for idx, opt in enumerate(q.options):
                lab = ET.SubElement(render, 'response_label', {'ident': f'ID_{idx}'})
                ET.SubElement(ET.SubElement(lab, 'material'), 'mattext').text = opt

            if q.type == "multiple_answers_question":
                cond = ET.SubElement(resproc, 'respcondition', {'continue': 'No'})
                cvar = ET.SubElement(cond, 'conditionvar')
                and_logic = ET.SubElement(cvar, 'and')
                for c_idx in q.corrects:
                    ET.SubElement(and_logic, 'varequal', {'respident': 'response1'}).text = f'ID_{c_idx}'
                ET.SubElement(cond, 'setvar', {'action': 'Set', 'varname': 'SCORE'}).text = '100'
            elif q.corrects:
                cond = ET.SubElement(resproc, 'respcondition', {'continue': 'No'})
                ET.SubElement(ET.SubElement(cond, 'conditionvar'), 'varequal', {'respident': 'response1'}).text = f'ID_{q.corrects[0]}'
                ET.SubElement(cond, 'setvar', {'action': 'Set', 'varname': 'SCORE'}).text = '100'

    with zipfile.ZipFile(output_zip, 'w') as z:
        z.writestr('assessment.xml', ET.tostring(root, encoding='utf-8', xml_declaration=True))
        z.writestr('imsmanifest.xml', '<?xml version="1.0" encoding="UTF-8"?><manifest identifier="MANIFEST_1" xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"><resources><resource identifier="RES_ASMT1" type="imsqti_xmlv1p2" href="assessment.xml"><file href="assessment.xml"/></resource></resources></manifest>')
    return True

def convert_to_qti_zip(input_file: Path, output_zip: Path):
    try:
        ext = input_file.suffix.lower()
        if ext == '.docx': questions = parse_docx(input_file)
        elif ext in ['.txt', '.md']:
            with open(input_file, 'r', encoding='utf-8') as f: questions = parse_text_based(f.read())
        elif ext == '.csv':
            questions = []
            with open(input_file, newline='', encoding='utf-8') as f:
                content = f.read().lstrip('\ufeff') # Clean BOM if present
                reader = csv.DictReader(io.StringIO(content))

                for i, row in enumerate(reader, 1):
                    raw_type = row.get('Type', '').upper()
                    prompt = row.get('Question', '')
                    if not prompt: continue

                    q_type = "multiple_choice_question"
                    if raw_type == 'MR': q_type = "multiple_answers_question"
                    elif raw_type == 'TF': q_type = "true_false_question"
                    elif raw_type == 'MATCHING': q_type = "matching_question"
                    elif raw_type == 'FIB': q_type = "fill_in_multiple_blanks_question"
                    elif raw_type == 'NUMERIC': q_type = "numerical_question"
                    elif raw_type in ['FORMULA', 'ESSAY']: q_type = "essay_question"
                    elif raw_type == 'FILEUPLOAD': q_type = "file_upload_question"

                    options = []
                    for j in range(1, 10):
                        c = row.get(f'Choice{j}')
                        if c and c.strip(): options.append(c.strip())

                    corrects = []
                    ans_str = row.get('Answer', '').strip()

                    if q_type == 'matching_question':
                        pass # Handled by options containing "->"
                    elif q_type in ['numerical_question', 'fill_in_multiple_blanks_question']:
                        if ans_str: options.append(ans_str)
                        corrects = [0] if options else []
                    elif q_type not in ['essay_question', 'file_upload_question']:
                        if q_type == 'multiple_answers_question':
                            for digit in ans_str: # e.g. "124" means options 1, 2, and 4
                                if digit.isdigit() and int(digit) > 0:
                                    corrects.append(int(digit) - 1)
                        else:
                            if ans_str in options:
                                corrects.append(options.index(ans_str))
                            elif ans_str.isdigit() and int(ans_str) > 0:
                                corrects.append(int(ans_str) - 1)

                    questions.append(Question(i, q_type, prompt, options, corrects))
        else: return False
        return build_qti_package(questions, output_zip, input_file.stem)
    except: return False
