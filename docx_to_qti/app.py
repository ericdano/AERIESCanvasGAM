from flask import Flask, request, send_file, render_template_string, jsonify
import os
import zipfile
import tempfile
from pathlib import Path
from io import BytesIO
import docx_to_qti #

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AUHSD QTI Converter</title>
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
<body class="bg-gray-100 min-h-screen p-6 font-sans">
    <div class="max-w-3xl mx-auto space-y-6">
        
        <div class="bg-white rounded-2xl shadow-xl p-10 border border-gray-200">
            <div class="flex justify-between items-start mb-8">
                <div>
                    <h1 class="text-3xl font-extrabold text-gray-900 tracking-tight">AUHSD QTI Converter</h1>
                    <p class="text-gray-500 mt-2">Convert Word (.docx) quizzes into LMS-ready QTI packages.</p>
                </div>
                <a href="/download-template" class="text-sm font-semibold text-blue-600 bg-blue-50 px-4 py-2 rounded-lg hover:bg-blue-100 transition flex items-center">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Template
                </a>
            </div>

            <form id="upload-form" action="/" method="post" enctype="multipart/form-data">
                <div id="drop-zone" class="group border-2 border-dashed border-gray-300 rounded-xl p-12 text-center cursor-pointer transition-all hover:border-blue-500 hover:bg-blue-50 mb-8">
                    <p class="text-gray-600 text-lg">Drag & drop files here or <span class="text-blue-600 font-semibold">browse</span></p>
                    <input type="file" name="files" id="file-input" multiple class="hidden" accept=".docx">
                </div>

                <div id="file-list" class="space-y-3 mb-8"></div>

                <button type="submit" id="submit-btn" class="w-full bg-blue-600 text-white font-bold py-4 rounded-xl hover:bg-blue-700 transition shadow-lg hidden flex items-center justify-center">
                    <span id="btn-text">Convert & Download All</span>
                </button>
            </form>
            <div id="status-area" class="mt-4 text-center text-sm font-medium text-blue-600 hidden"></div>
        </div>

        <div class="bg-white rounded-2xl shadow-md p-8 border border-gray-200">
            <h2 class="text-xl font-bold text-gray-800 mb-4 flex items-center">
                <svg class="w-5 h-5 mr-2 text-yellow-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
                Formatting Requirements
            </h2>
            <div class="grid md:grid-cols-2 gap-6 text-sm">
                <div class="space-y-2">
                    <h3 class="font-bold text-gray-700 uppercase tracking-wider">1. Question Headers</h3>
                    <p class="text-gray-600">Every question must start with the word <code class="bg-gray-100 px-1 rounded text-red-600">Question</code> followed by a number.</p>
                    <div class="bg-gray-50 p-3 rounded border font-mono text-xs">
                        Question 1<br>
                        What is 2+2?
                    </div>
                </div>
                <div class="space-y-2">
                    <h3 class="font-bold text-gray-700 uppercase tracking-wider">2. Correct Answers</h3>
                    <p class="text-gray-600">Mark correct choices by using the <strong>Highlight tool</strong> (Yellow) in Word.</p>
                    <div class="bg-gray-50 p-3 rounded border font-mono text-xs">
                        A. 3<br>
                        <span class="bg-yellow-200 px-1">B. 4</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // ... (Same JavaScript as previous response) ...
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
                item.className = 'flex items-center justify-between bg-gray-50 border border-gray-200 p-4 rounded-lg';
                item.innerHTML = `<span>${file.name}</span><button type="button" onclick="removeFile(${index})" class="text-red-500">✕</button>`;
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
            btnText.innerHTML = '<span class="spinner"></span>Processing...';
            statusArea.classList.remove('hidden');
            statusArea.textContent = 'Generating individual QTI packages...';

            const dataTransfer = new DataTransfer();
            selectedFiles.forEach(file => dataTransfer.items.add(file));
            fileInput.files = dataTransfer.files;
        };
    </script>
</body>
</html>
'''

# ... (Rest of upload_file and download_template routes remain the same) ...

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        uploaded_files = request.files.getlist('files')
        output_zips = []
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            for file in uploaded_files:
                if file.filename.endswith('.docx'):
                    safe_name = Path(file.filename).stem
                    input_docx = tmp_path / file.filename
                    file.save(str(input_docx))
                    indiv_zip_path = tmp_path / f"{safe_name}_qti.zip"
                    success = docx_to_qti.convert_docx_to_qti_zip(input_docx, indiv_zip_path)
                    if success:
                        output_zips.append(indiv_zip_path)

            if not output_zips:
                return "Conversion failed. Ensure your DOCX follows the Question/Highlight format.", 400

            master_zip_buffer = BytesIO()
            with zipfile.ZipFile(master_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as master:
                for z in output_zips:
                    master.write(z, arcname=z.name)
            master_zip_buffer.seek(0)
            return send_file(master_zip_buffer, mimetype='application/zip', as_attachment=True, download_name='qti_conversions.zip')
    return render_template_string(HTML_TEMPLATE)

@app.route('/download-template')
def download_template():
    from docx import Document
    from docx.enum.text import WD_COLOR_INDEX
    doc = Document()
    doc.add_heading('QTI Formatting Example', 0)
    doc.add_paragraph('Question 1') #
    doc.add_paragraph('What color is the sky?')
    doc.add_paragraph('A. Green')
    ans = doc.add_paragraph('B. Blue')
    ans.runs[0].font.highlight_color = WD_COLOR_INDEX.YELLOW #
    f = BytesIO(); doc.save(f); f.seek(0)
    return send_file(f, as_attachment=True, download_name="QTI_Template.docx")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)