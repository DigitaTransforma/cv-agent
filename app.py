import os
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import google.generativeai as genai
from PyPDF2 import PdfReader
from docx import Document
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

# Configure Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    with open(file_path, 'rb') as file:
        reader = PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
    return text

def extract_text_from_doc(file_path):
    doc = Document(file_path)
    return ' '.join([paragraph.text for paragraph in doc.paragraphs])

def analyze_cv(cv_text, job_description):
    prompt = f"""
    As an expert CV analyzer, review this CV against the job description provided.
    
    CV: {cv_text}
    
    Job Description: {job_description}
    
    Provide a detailed analysis with the following format:

    # CV Analysis Summary

    ## Match Score
    - Overall match percentage with explanation
    
    ## Key Missing Skills & Experience
    - Bullet point each missing skill or experience
    - Include brief explanation for each point
    
    ## Areas for Improvement
    1. [Area 1]
       - Specific recommendations
       - Action items
    
    2. [Area 2]
       - Specific recommendations
       - Action items
    
    ## Strengths
    - Bullet point each strength that aligns with the role
    - Include how each strength relates to the job requirements
    
    ## Action Plan
    1. First priority action
       - Details and implementation steps
    2. Second priority action
       - Details and implementation steps
    3. Third priority action
       - Details and implementation steps

    Note: Format the response using proper markdown with clear headings, bullet points, and numbered lists.
    Ensure there is proper spacing between sections.
    """
    
    response = model.generate_content(prompt)
    return response.text

def optimize_cv(cv_text, job_description):
    prompt = f"""
    As an expert CV optimizer, first extract all personal information from the CV, then rewrite it to better match the job description while maintaining truthfulness.

    Original CV: {cv_text}
    
    Job Description: {job_description}
    
    IMPORTANT: First, carefully extract all personal information from the CV and ensure it appears at the beginning of the response.
    
    Please structure the response exactly as follows, starting with personal information:

    # Optimized CV

    ## Personal Information
    IMPORTANT - Extract and include these details from the original CV:
    - Full Name: [Extract if available in CV]
    - Email Address: [Extract if available in CV]
    - Phone Number: [Extract if available in CV]
    - Location: [Extract if available in CV]
    - LinkedIn: [Extract if available in CV]

    ## Professional Summary
    [Compelling summary tailored to the role]

    ## Key Skills
    - Skill Category 1
      - Relevant skill 1
      - Relevant skill 2
    - Skill Category 2
      - Relevant skill 1
      - Relevant skill 2

    ## Professional Experience
    ### [Company Name] | [Position] | [Dates]
    - Achievement 1 with metrics
    - Achievement 2 with metrics
    - Achievement 3 with metrics

    ## Education
    ### [Degree] | [Institution] | [Year]
    - Relevant coursework
    - Academic achievements

    ## Additional Information
    - Certifications
    - Languages
    - Relevant volunteer work

    CRITICAL INSTRUCTIONS:
    1. MUST start with Personal Information section
    2. MUST extract and display actual personal details from the CV
    3. DO NOT use placeholder text for personal information
    4. Use proper markdown formatting with clear headings and consistent spacing
    5. Use strong action verbs and quantifiable achievements
    6. Maintain all truthful information while optimizing presentation
    """
    
    response = model.generate_content(prompt)
    return response.text

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'cv' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['cv']
        job_description = request.form.get('job_description', '')
        action = request.form.get('action', '')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Ensure upload directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            try:
                file.save(filepath)
                
                # Extract text based on file type
                try:
                    if filename.endswith('.pdf'):
                        cv_text = extract_text_from_pdf(filepath)
                    else:
                        cv_text = extract_text_from_doc(filepath)
                except Exception as e:
                    return jsonify({'error': f'Error reading file: {str(e)}'}), 400
                finally:
                    # Clean up the uploaded file
                    if os.path.exists(filepath):
                        os.remove(filepath)
                
                # Process based on action
                try:
                    if action == 'analyze':
                        result = analyze_cv(cv_text, job_description)
                    else:  # optimize
                        result = optimize_cv(cv_text, job_description)
                    
                    return jsonify({'result': result})
                except Exception as e:
                    return jsonify({'error': f'Error processing CV: {str(e)}'}), 500
                
            except Exception as e:
                return jsonify({'error': f'Error saving file: {str(e)}'}), 500
        
        return jsonify({'error': 'Invalid file type'}), 400
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Use environment variables for production
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
