from flask import Flask, request, send_file, render_template_string, jsonify
import os
import zipfile
import tempfile
from pathlib import Path
from io import BytesIO
import docx_to_qti  #

app = Flask(__name__)

# Modern HTML with Tailwind CSS for styling and Vanilla JS for file management
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QTI Converter Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .drop-zone--over { border-color: #3b82f6; background-color: #eff6ff; }
    </style>
</head>
<body class="bg-gray-50 min-h-screen flex items-center justify-center p-6">
    <div class="max-w-2xl w-full bg-white rounded-xl shadow-lg p-8">
        <h1 class="text-3xl font-bold text-gray-800 mb-2">DOCX to QTI Converter</h1>
        <p class="text-gray-600 mb-8">Convert your Word documents into QTI packages for Canvas, Moodle, or Blackboard.</p>

        <form id="upload-form" action="/" method="post" enctype="multipart/form-data">
            <div id="drop-zone" class="border-2 border-dashed border-gray-300 rounded-lg p-10 text-center cursor-pointer transition-all hover:border-blue-400 mb-6">
                <p class="text-gray-500 text-lg">Drag & drop .docx files here or <span class="text-blue-500 font-medium">click to browse</span></p>
                <input type="file" name="files" id="file-input" multiple class="hidden" accept=".docx">
            </div>

            <div id="file-list" class="space-y-3 mb-6"></div>

            <button type="submit" id="submit-btn" class="w-full bg-blue-600 text-white font-semibold py-3 rounded-lg hover:bg-blue-700 transition hidden">
                Convert & Download
            </button>
        </form>
    </div>

    <script>
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const fileList = document.getElementById('file-list');
        const submitBtn = document.getElementById('submit-btn');
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
                if (file.name.endsWith('.docx')) {
                    selectedFiles.push(file);
                }
            }
            renderFileList();
        }

        function renderFileList() {
            fileList.innerHTML = '';
            selectedFiles.forEach((file, index) => {
                const item = document.createElement('div');
                item.className = 'flex items-center justify-between bg-gray-100 p-3 rounded-md';
                item.innerHTML = `
                    <span class="text-gray-700 truncate">${file.name}</span>
                    <button type="button" onclick="removeFile(${index})" class="text-red-500 hover:text-red-700 font-bold px-2">✕</button>
                `;
                fileList.appendChild(item);
            });
            submitBtn.classList.toggle('hidden', selectedFiles.length === 0);
        }

        window.removeFile = (index) => {
            selectedFiles.splice(index, 1);
            renderFileList();
        };

        document.getElementById('upload-form').onsubmit = (e) => {
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
                    safe_filename = Path(file.filename).stem
                    input_docx = tmp_path / file.filename
                    file.save(str(input_docx))
                    
                    # Create the individual ZIP with the specific name
                    out_zip_name = f"{safe_filename}_qti.zip"
                    out_zip_path = tmp_path / out_zip_name
                    
                    success = docx_to_qti.convert_docx_to_qti_zip(input_docx, out_zip_path)
                    
                    if success:
                        output_zips.append(out_zip_path)

            if not output_zips:
                return "Conversion failed. Ensure your DOCX follows the required format (Questions & Highlights).", 400

            # Package all individual ZIPS into one final bundle for the user
            master_zip_buffer = BytesIO()
            with zipfile.ZipFile(master_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as master_zip:
                for z_file in output_zips:
                    # This places ExampleQuiz_qti.zip inside the main download
                    master_zip.write(z_file, arcname=z_file.name)
            
            master_zip_buffer.seek(0)
            return send_file(
                master_zip_buffer, 
                mimetype='application/zip', 
                as_attachment=True, 
                download_name='qti_conversions.zip'
            )

    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)