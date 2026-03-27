#!/usr/bin/env python3
from pathlib import Path
import sys, os, re, zipfile, shutil, logging
from collections import namedtuple
from xml.etree import ElementTree as ET
from docx import Document
'''
Converts a .docx file containing quiz questions into a QTI 1.2 compliant ZIP package.
- Parses questions based on "Question X" headings.
- Detects question types (MCQ, FIB, Matching, Essay) based on content and formatting (e.g., highlighted options).
- Generates XML files for the assessment and manifest, then packages them into a ZIP file for import into LMS platforms that support QTI.   


'''


# Data structure for parsed question
Question = namedtuple("Question", ["number", "prompt_html", "options_html", "correct_indices", "is_fib", "is_matching"])

def convert_docx_to_qti_zip(input_docx, output_zip):
    try:
        doc = Document(str(input_docx))
        questions = []
        paras = doc.paragraphs
        q_num = 0
        
        i = 0
        while i < len(paras):
            text = paras[i].text.strip()
            if re.match(r'^Question\s+\d+', text, re.I):
                q_num += 1
                prompt = paras[i+1].text.strip()
                i += 2
                options = []
                corrects = []
                
                # Collect options until next Question or end
                while i < len(paras) and not re.match(r'^Question\s+\d+', paras[i].text.strip(), re.I):
                    opt_text = paras[i].text.strip()
                    if opt_text:
                        options.append(opt_text)
                        # Check for highlight in any run of the paragraph
                        if any(run.font.highlight_color for run in paras[i].runs):
                            corrects.append(len(options) - 1)
                    i += 1
                
                is_fib = "[" in prompt and "]" in prompt
                is_matching = all("->" in o for o in options) and len(options) > 0
                
                questions.append(Question(q_num, prompt, options, corrects, is_fib, is_matching))
            else:
                i += 1

        # Build XML
        build_qti_files(questions, output_zip)
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def build_qti_files(questions, output_zip):
    NS = "http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
    root = ET.Element('questestinterop', {'xmlns': NS})
    assess = ET.SubElement(root, 'assessment', {'ident': 'ASMT_1', 'title': 'Imported Quiz'})
    section = ET.SubElement(assess, 'section', {'ident': 'root_section'})

    for q in questions:
        item = ET.SubElement(section, 'item', {'ident': f'ITEM_{q.number}'})
        
        # Metadata for type
        q_type = "multiple_choice_question"
        if q.is_fib: q_type = "fill_in_multiple_blanks_question"
        elif q.is_matching: q_type = "matching_question"
        elif not q.options_html: q_type = "essay_question"
        elif len(q.correct_indices) > 1: q_type = "multiple_answer_question"
        elif len(q.options_html) == 2 and any(o.lower() == "true" for o in q.options_html): q_type = "true_false_question"

        # Material (Prompt)
        pres = ET.SubElement(item, 'presentation')
        mat = ET.SubElement(pres, 'material')
        ET.SubElement(mat, 'mattext', {'texttype': 'text/html'}).text = q.prompt_html

        # Response Processing Logic
        if q_type == "fill_in_multiple_blanks_question":
            res_str = ET.SubElement(pres, 'response_str', {'ident': 'response1', 'rcardinality': 'Single'})
            ET.SubElement(res_str, 'render_fib', {'fibtype': 'String'})
        elif q_type != "essay_question":
            res_lid = ET.SubElement(pres, 'response_lid', {'ident': 'res1', 'rcardinality': 'Single'})
            render = ET.SubElement(res_lid, 'render_choice')
            for idx, opt in enumerate(q.options_html):
                resp_lab = ET.SubElement(render, 'response_label', {'ident': f'ID_{idx}'})
                mat_c = ET.SubElement(resp_lab, 'material')
                ET.SubElement(mat_c, 'mattext').text = opt

    # Simplified packaging for demonstration
    with zipfile.ZipFile(output_zip, 'w') as z:
        z.writestr('assessment.xml', ET.tostring(root))
        z.writestr('imsmanifest.xml', '<?xml version="1.0" encoding="UTF-8"?><manifest identifier="man1"><resources><resource identifier="res1" type="imsqti_xmlv1p2" href="assessment.xml"><file href="assessment.xml"/></resource></resources></manifest>')