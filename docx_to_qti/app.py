from flask import Flask, request, send_file, render_template_string
import os
import zipfile
import tempfile
from pathlib import Path
from io import BytesIO
import docx_to_qti  # Ensure docx_to_qti.py is in the same folder

app = Flask(__name__)

# Ultimate UI Template with Footer and Modern Components
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AUHSD QTI Converter Ultimate</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .drop-zone--over { border-color: #3b82f6; background-color: #eff6ff; }
        .spinner {
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top: 3px solid #fff;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-right: 10px;
            vertical-align: middle;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-gray-100 min-h-screen p-4 md:p-10 font-sans flex flex-col">
    <div class="max-w-4xl mx-auto space-y-8 flex-grow">
        
        <div class="bg-white rounded-3xl shadow-2xl p-8 md:p-12 border border-gray-100">
            <div class="flex flex-col md:flex-row justify-between items-start mb-10">
                <div class="mb-4 md:mb-0">
                    <h1 class="text-4xl font-black text-gray-900 tracking-tight">AUHSD QTI Converter</h1>
                    <p class="text-gray-500 mt-2 text-lg">Batch convert Word documents to LMS-ready QTI packages.</p>
                </div>
                <a href="/download-template" class="inline-flex items-center px-5 py-3 bg-blue-50 text-blue-700 font-bold rounded-xl hover:bg-blue-100 transition duration-200">
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Download Template
                </a>
            </div>

            <form id="upload-form" action="/" method="post" enctype="multipart/form-data">
                <div id="drop-zone" class="group border-3 border-dashed border-gray-200 rounded-2xl p-16 text-center cursor-pointer transition-all hover:border-blue-400 hover:bg-blue-50/50 mb-8">
                    <div class="bg-blue-100 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                    </div>
                    <p class="text-xl text-gray-600">Drag & drop quiz files here or <span class="text-blue-600 font-bold underline">browse files</span></p>
                    <input type="file" name="files" id="file-input" multiple class="hidden" accept=".docx">
                </div>

                <div id="file-list" class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8"></div>

                <button type="submit" id="submit-btn" class="w-full bg-blue-600 text-white font-black py-5 rounded-2xl hover:bg-blue-700 transition-all shadow-xl shadow-blue-200 hidden transform hover:-translate-y-1">
                    <span id="btn-text" class="text-lg uppercase tracking-widest">Convert & Download All</span>
                </button>
            </form>
            
            <div id="status-area" class="mt-6 text-center text-blue-600 font-bold hidden"></div>
        </div>

        <div class="bg-white rounded-3xl shadow-lg p-8 border border-gray-100">
            <h2 class="text-2xl font-black text-gray-800 mb-6 flex items-center uppercase tracking-wide">
                <span class="w-8 h-8 bg-yellow-400 text-white rounded-lg flex items-center justify-center mr-3 text-sm font-bold">!</span>
                Quick Formatting Guide
            </h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8 text-sm">
                <div class="p-4 bg-gray-50 rounded-xl">
                    <h3 class="font-black text-blue-600 mb-2">Structure</h3>
                    <p class="text-gray-600">Use <code class="bg-blue-100 px-1 rounded text-blue-800 font-bold">Question X</code> as your header before every question prompt.</p>
                </div>
                <div class="p-4 bg-gray-50 rounded-xl">
                    <h3 class="font-black text-blue-600 mb-2">Answers</h3>
                    <p class="text-gray-600">Mark correct choices by applying a <span class="bg-yellow-200 px-1 font-bold">Yellow Highlight</span> to the text in Word.</p>
                </div>
                <div class="p-4 bg-gray-50 rounded-xl">
                    <h3 class="font-black text-blue-600 mb-2">Special Types</h3>
                    <p class="text-gray-600">Use <code class="bg-blue-100 px-1 rounded text-blue-800 font-bold">-></code> for Matching and <code class="bg-blue-100 px-1 rounded text-blue-800 font-bold">[ ]</code> for Fill in the Blank.</p>
                </div>
            </div>
        </div>
    </div>

    <footer class="max-w-4xl mx-auto w-full py-8 text-center text-gray-400 text-sm font-medium">
        <p>Copyright 2026 by Eric Dannewitz and Gemini</p>
    </footer>

    <script>
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const fileList = document.getElementById('file-list');
        const submitBtn = document.getElementById('submit-btn');
        const btnText = document.getElementById('btn-text');
        const statusArea = document.getElementById('status-area');
        const form = document.getElementById('upload-form');
        let selectedFiles = [];

        dropZone.onclick = () => fileInput.click();
        fileInput.onchange = (e) => handleFiles(e.target.files);
        dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('drop-zone--over'); };
        dropZone.ondragleave = () => dropZone.classList.remove('drop-zone--over');
        dropZone.ondrop = (e) => {
            e.preventDefault();
            dropZone.classList.remove('drop-zone--over');
            handleFiles(e.dataTransfer.files);
        };

        function handleFiles(files) {
            for (const file of files) {
                if (file.name.endsWith('.docx') && !selectedFiles.some(f => f.name === file.name)) {
                    selectedFiles.push(file);
                }
            }
            renderFileList();
        }

        function renderFileList() {
            fileList.innerHTML = '';
            selectedFiles.forEach((file, index) => {
                const item = document.createElement('div');
                item.className = 'flex items-center justify-between bg-white border border-gray-200 p-4 rounded-xl shadow-sm';
                item.innerHTML = `
                    <div class="flex items-center overflow-hidden">
                        <div class="p-2 bg-blue-50 rounded-lg mr-3">
                           <svg class="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20"><path d="M4 4a2 2 0 012-2h4.586A1 1 0 0111 2.414l4.293 4.293V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"></path></svg>
                        </div>
                        <span class="text-gray-700 font-bold truncate">${file.name}</span>
                    </div>
                    <button type="button" onclick="removeFile(${index})" class="text-gray-300 hover:text-red-500 transition-colors px-2 text-xl font-black">✕</button>
                `;
                fileList.appendChild(item);
            });
            submitBtn.classList.toggle('hidden', selectedFiles.length === 0);
        }

        window.removeFile = (index) => {
            selectedFiles.splice(index, 1);
            renderFileList();
        };

        form.onsubmit = (e) => {
            submitBtn.disabled = true;
            btnText.innerHTML = '<span class="spinner"></span>Finalizing Packages...';
            statusArea.classList.remove('hidden');
            statusArea.textContent = 'Analyzing document structures...';

            const dataTransfer = new DataTransfer();
            selectedFiles.forEach(file => dataTransfer.items.add(file));
            fileInput.files = dataTransfer.files;
        };
    </script>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or uploaded_files[0].filename == '':
            return "No files selected", 400

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            output_zips = []

            for file in uploaded_files:
                if file.filename.endswith('.docx'):
                    clean_name = Path(file.filename).stem
                    input_docx = tmp_path / file.filename
                    file.save(str(input_docx))
                    
                    indiv_zip = tmp_path / f"{clean_name}_qti.zip"
                    
                    # Process via the docx_to_qti.py logic
                    if docx_to_qti.convert_docx_to_qti_zip(input_docx, indiv_zip):
                        output_zips.append(indiv_zip)

            if not output_zips:
                return "Conversion failed. Please ensure the DOCX follows the Question/Highlight format.", 400

            master_zip_buffer = BytesIO()
            with zipfile.ZipFile(master_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as master:
                for z in output_zips:
                    master.write(z, arcname=z.name)
            
            master_zip_buffer.seek(0)
            return send_file(
                master_zip_buffer, 
                mimetype='application/zip', 
                as_attachment=True, 
                download_name='qti_conversions_batch.zip'
            )

    return render_template_string(HTML_TEMPLATE)

@app.route('/download-template')
def download_template():
    from docx import Document
    from docx.enum.text import WD_COLOR_INDEX
    doc = Document()
    doc.add_heading('QTI Ultimate Template', 0)
    
    doc.add_paragraph('Question 1') #
    doc.add_paragraph('Multiple Choice: What color is the sun?')
    ans = doc.add_paragraph('Yellow')
    ans.runs[0].font.highlight_color = WD_COLOR_INDEX.YELLOW #
    doc.add_paragraph('Purple')

    doc.add_paragraph('\nQuestion 2')
    doc.add_paragraph('Matching: France -> Paris') #
    doc.add_paragraph('Germany -> Berlin')

    doc.add_paragraph('\nQuestion 3')
    doc.add_paragraph('Fill-in-the-blank: Water is made of [hydrogen] and oxygen.')

    f = BytesIO(); doc.save(f); f.seek(0)
    return send_file(f, as_attachment=True, download_name="QTI_Template_Collaborative.docx")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)