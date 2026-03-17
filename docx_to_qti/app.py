from flask import Flask, request, send_file, render_template_string
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from io import BytesIO

# Import your existing logic (assuming the script is named docx_to_qti.py)
# Or paste the conversion functions (convert_docx_to_qti_zip, etc.) directly here.
import docx_to_qti 

app = Flask(__name__)

# Simple HTML Interface
HTML_TEMPLATE = '''
<!doctype html>
<title>DOCX to QTI Converter</title>
<h1>Upload DOCX files to convert</h1>
<form method=post enctype=multipart/form-data>
  <input type=file name=files multiple>
  <input type=submit value=Convert>
</form>
'''

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or uploaded_files[0].filename == '':
            return "No files selected", 400

        # Create a unique temporary directory for this request
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            output_zips = []

            for file in uploaded_files:
                if file and file.filename.endswith('.docx'):
                    # Save the uploaded file
                    input_path = tmp_path / file.filename
                    file.save(str(input_path))
                    
                    # Define output name
                    out_zip = tmp_path / (input_path.stem + "_qti.zip")
                    
                    # Call your existing conversion logic
                    success = docx_to_qti.convert_docx_to_qti_zip(input_path, out_zip)
                    if success:
                        output_zips.append(out_zip)

            if not output_zips:
                return "No valid questions found in uploaded files.", 400

            # If only one file, send it directly
            if len(output_zips) == 1:
                return send_file(output_zips[0], as_attachment=True)

            # If multiple, bundle them into one master ZIP
            master_zip_buffer = BytesIO()
            with zipfile.ZipFile(master_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as master_zip:
                for z_file in output_zips:
                    master_zip.write(z_file, arcname=z_file.name)
            
            master_zip_buffer.seek(0)
            return send_file(
                master_zip_buffer, 
                mimetype='application/zip', 
                as_attachment=True, 
                download_name='converted_qti_packages.zip'
            )

    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(debug=True, port=5000)