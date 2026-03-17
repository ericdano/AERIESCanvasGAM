from flask import Flask, request, send_file, render_template_string
import os
import zipfile
import tempfile
from pathlib import Path
from io import BytesIO

# Import the conversion function from your original script
import docx_to_qti

app = Flask(__name__)

HTML_TEMPLATE = '''
<!doctype html>
<html>
<head><title>DOCX to QTI Converter</title></head>
<body>
    <h1>DOCX to QTI Converter</h1>
    <p>Upload one or more DOCX files to convert them to QTI ZIP packages.</p>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="files" multiple>
        <input type="submit" value="Convert">
    </form>
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
                    input_path = tmp_path / file.filename
                    file.save(str(input_path))
                    
                    # Target output path for this specific docx
                    out_zip = tmp_path / (input_path.stem + "_qti.zip")
                    
                    # Execute the logic from your docx_to_qti.py
                    success = docx_to_qti.convert_docx_to_qti_zip(input_path, out_zip)
                    
                    if success:
                        output_zips.append(out_zip)

            if not output_zips:
                return "Conversion failed for all files. Check docx_to_qti.log.", 400

            # If multiple files, bundle them into one master ZIP
            master_zip_buffer = BytesIO()
            with zipfile.ZipFile(master_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as master_zip:
                for z_file in output_zips:
                    master_zip.write(z_file, arcname=z_file.name)
            
            master_zip_buffer.seek(0)
            return send_file(
                master_zip_buffer, 
                mimetype='application/zip', 
                as_attachment=True, 
                download_name='all_qti_packages.zip'
            )

    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Listen on all interfaces so Docker can route traffic
    app.run(host='0.0.0.0', port=5000)