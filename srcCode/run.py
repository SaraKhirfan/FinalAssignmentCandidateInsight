import os
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv

# ✅ STEP 1: LOAD .ENV FIRST
load_dotenv(override=True)

# ✅ STEP 2: GET API KEY
api_key = os.getenv('MY_CUSTOM_AI_KEY')

# ✅ STEP 3: VERIFY API KEY
print("\n" + "=" * 70)
print("🔑 API KEY VERIFICATION")
print("=" * 70)
if api_key and api_key.startswith('sk-'):

    print(f"✅ Length: {len(api_key)} characters")
else:
    print(f"❌ INVALID OR MISSING API KEY!")
    print(f"❌ Current value: {api_key}")
    print(f"❌ Check your .env file!")
print("=" * 70 + "\n")

# ✅ STEP 4: NOW IMPORT FLASK AND OTHER MODULES
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from app.resume_parser import ResumeParser
from app.job_matcher import JobMatcher

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_if_env_fails')

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads/resumes'
app.config['JOB_DESC_FOLDER'] = 'uploads/job_descriptions'
app.config['PARSED_FOLDER'] = 'data/parsed_resumes'
app.config['JOBS_DATA_FILE'] = 'data/jobs.json'
app.config['MY_CUSTOM_AI_KEY'] = api_key
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# ✅ STEP 5: Initialize AI components
parser = ResumeParser(api_key=api_key)
matcher = JobMatcher(api_key=api_key)

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def load_jobs():
    """Load jobs from JSON file"""
    if os.path.exists(app.config['JOBS_DATA_FILE']):
        with open(app.config['JOBS_DATA_FILE'], 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_jobs(jobs):
    """Save jobs to JSON file"""
    os.makedirs('data', exist_ok=True)
    with open(app.config['JOBS_DATA_FILE'], 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

def get_resumes_list():
    """Get list of parsed resumes"""
    resumes = []
    if os.path.exists(app.config['PARSED_FOLDER']):
        for filename in os.listdir(app.config['PARSED_FOLDER']):
            if filename.endswith('.json'):
                # CRITICAL FIX: Keep full filename as ID for API matching
                resumes.append({
                    'id': filename,  # ← Keep .json extension!
                    'name': filename.replace('.pdf.json', '.pdf'),  # Display name
                    'filename': filename
                })
    return resumes

def get_selected_job():
    """Get the currently selected job"""
    jobs = load_jobs()
    for job in jobs:
        if job.get('selected', False):
            return job
    return None

# =====================================================
# MAIN PAGE ROUTES
# =====================================================

@app.route('/')
def index():
    """Splash screen - redirects to resumes page"""
    return render_template('index.html')

@app.route('/help')
def help_page():
    """Help and guide page"""
    return render_template('help.html')

@app.route('/resumes')
def resumes_page():
    """Resume management page"""
    resumes = get_resumes_list()
    return render_template('resumes.html', resumes=resumes)

@app.route('/jobs')
def jobs_page():
    """Job description management page"""
    jobs = load_jobs()
    resumes = get_resumes_list()
    selected_job = get_selected_job()
    
    return render_template('jobs.html', 
                         jobs=jobs, 
                         resume_count=len(resumes),
                         selected_job=selected_job)

@app.route('/results')
def results_page():
    """Match results page"""
    # Get results from session
    results = session.get('match_results', [])
    job_title = session.get('job_title', '')
    job_description = session.get('job_description', '')
    
    # Get total number of resumes analyzed
    total_resumes = len(get_resumes_list())
    
    return render_template('results.html', 
                         results=results,
                         job_title=job_title,
                         job_description=job_description,
                         total_resumes=total_resumes)

# =====================================================
# RESUME OPERATIONS
# =====================================================

@app.route('/upload-resumes', methods=['POST'])
def upload_resumes():
    """Upload and parse resumes"""
    print("\n" + "=" * 70)
    print("📤 UPLOAD REQUEST")
    print("=" * 70)
    
    if 'resumes' not in request.files:
        print("❌ No files in request")
        flash("No resumes selected.", "warning")
        return redirect(url_for('resumes_page'))
    
    files = request.files.getlist('resumes')
    print(f"📁 Files: {len(files)}")
    
    parsed_count = 0
    failed_count = 0
    
    for file in files:
        if file.filename:
            print(f"\n📄 {file.filename}")
            
            # Validate file type
            if not file.filename.lower().endswith('.pdf'):
                print(f"   ❌ Not a PDF file")
                failed_count += 1
                continue
            
            try:
                # Save file
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(path)
                print(f"   ✓ Saved")
                
                # Extract text from PDF
                print(f"   📖 Extracting PDF...")
                text = parser.extract_text_from_pdf(path)
                
                # Parse with AI
                if text and len(text.strip()) > 50:
                    print(f"   ✓ {len(text)} chars extracted")
                    print(f"   🤖 Calling OpenAI...")
                    
                    parsed_json = parser.parse_resume(text)
                    
                    # Check if validation failed (not a CV)
                    if parsed_json and parsed_json.get('error') == 'NOT_A_CV':
                        print(f"   ❌ NOT A CV: {parsed_json.get('message')}")
                        flash(f"⚠️ '{file.filename}' was rejected: {parsed_json.get('message')}", "warning")
                        failed_count += 1
                        continue
                    
                    if parsed_json and parsed_json.get('is_valid_cv', True):
                        print(f"   ✅ AI SUCCESS")
                        os.makedirs(app.config['PARSED_FOLDER'], exist_ok=True)
                        save_path = os.path.join(app.config['PARSED_FOLDER'], f"{file.filename}.json")
                        
                        with open(save_path, 'w', encoding='utf-8') as f:
                            json.dump(parsed_json, f, ensure_ascii=False, indent=2)
                        
                        print(f"   ✅ Saved: {save_path}")
                        parsed_count += 1
                    else:
                        print(f"   ❌ AI returned None or invalid")
                        failed_count += 1
                else:
                    print(f"   ❌ Text too short or extraction failed")
                    failed_count += 1
                    
            except Exception as e:
                print(f"   ❌ ERROR: {str(e)}")
                import traceback
                traceback.print_exc()
                failed_count += 1
    
    print(f"\n📊 SUCCESS: {parsed_count} | FAILED: {failed_count}")
    print("=" * 70 + "\n")
    
    if parsed_count > 0:
        flash(f"✅ Successfully processed {parsed_count} resume(s).", "success")
    if failed_count > 0:
        flash(f"⚠️ Failed to process {failed_count} resume(s). Only PDF files are supported.", "warning")
    
    return redirect(url_for('resumes_page'))

@app.route('/api/resumes/delete/<resume_id>', methods=['DELETE'])
def delete_resume(resume_id):
    """Delete a single resume"""
    try:
        # Delete parsed JSON
        json_path = os.path.join(app.config['PARSED_FOLDER'], f"{resume_id}.json")
        if os.path.exists(json_path):
            os.remove(json_path)
        
        # Delete original PDF
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], resume_id)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/resumes/delete-all', methods=['DELETE'])
def delete_all_resumes():
    """Delete all resumes"""
    try:
        # Delete all parsed JSONs
        if os.path.exists(app.config['PARSED_FOLDER']):
            for filename in os.listdir(app.config['PARSED_FOLDER']):
                os.remove(os.path.join(app.config['PARSED_FOLDER'], filename))
        
        # Delete all PDFs
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/resumes/view/<path:resume_id>')
def view_resume(resume_id):
    """View parsed resume data - handles both .pdf and .pdf.json IDs"""
    try:
        from urllib.parse import unquote
        
        # Decode URL-encoded name
        resume_id = unquote(resume_id)
        
        print(f"🔍 Looking for resume: {resume_id}")
        
        parsed_dir = app.config['PARSED_FOLDER']
        
        # Normalize the resume_id to match .json files
        # Handle cases: "name.pdf", "name.pdf.json", or just "name"
        search_patterns = []
        
        if resume_id.endswith('.pdf.json'):
            # Already correct format
            search_patterns.append(resume_id)
        elif resume_id.endswith('.pdf'):
            # Add .json extension
            search_patterns.append(f"{resume_id}.json")
        elif resume_id.endswith('.json'):
            # Keep as is
            search_patterns.append(resume_id)
        else:
            # Try both
            search_patterns.append(f"{resume_id}.pdf.json")
            search_patterns.append(f"{resume_id}.json")
        
        print(f"   🔍 Search patterns: {search_patterns}")
        
        # Try to find the resume file
        resume_data = None
        matched_file = None
        
        for filename in os.listdir(parsed_dir):
            if filename.endswith('.json'):
                # Check if filename matches any search pattern
                if filename in search_patterns:
                    filepath = os.path.join(parsed_dir, filename)
                    print(f"   ✅ Found exact match: {filename}")
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        resume_data = json.load(f)
                        matched_file = filename
                    break
                
                # Also try name matching from JSON content
                filepath = os.path.join(parsed_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        candidate_name = data.get('name', data.get('candidate_name', ''))
                        
                        # Match by candidate name
                        if candidate_name and (
                            candidate_name == resume_id or 
                            candidate_name.lower() == resume_id.lower()
                        ):
                            resume_data = data
                            matched_file = filename
                            print(f"   ✅ Found by name match: {filename}")
                            break
                            
                except Exception as e:
                    continue
        
        if not resume_data:
            print(f"   ❌ Resume not found: {resume_id}")
            print(f"   📋 Available files:")
            for f in os.listdir(parsed_dir):
                if f.endswith('.json'):
                    print(f"      - {f}")
            return jsonify({'error': 'Resume not found'}), 404
        
        # Return data in consistent format
        response = {
            'name': resume_data.get('name', resume_data.get('candidate_name', 'Unknown')),
            'email': resume_data.get('email', resume_data.get('contact', {}).get('email', '') if isinstance(resume_data.get('contact'), dict) else ''),
            'phone': resume_data.get('phone', resume_data.get('contact', {}).get('phone', '') if isinstance(resume_data.get('contact'), dict) else ''),
            'summary': resume_data.get('summary', resume_data.get('objective', resume_data.get('profile', ''))),
            'skills': resume_data.get('skills', resume_data.get('technical_skills', [])),
            'experience': resume_data.get('experience', resume_data.get('work_experience', resume_data.get('employment_history', ''))),
            'education': resume_data.get('education', resume_data.get('academic_background', ''))
        }
        
        print(f"   ✅ Returning data for: {response['name']}")
        return jsonify(response)
        
    except Exception as e:
        print(f"   ❌ Error in view_resume: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# =====================================================
# JOB OPERATIONS
# =====================================================

@app.route('/add-job', methods=['POST'])
def add_job():
    """Add a new job description"""
    print("\n" + "=" * 70)
    print("➕ ADD JOB REQUEST")
    print("=" * 70)
    
    job_title = request.form.get('job_title', '').strip()
    job_description = None
    
    # Check if job description file was uploaded
    if 'job_file' in request.files:
        file = request.files['job_file']
        
        if file and file.filename and file.filename.lower().endswith('.pdf'):
            print(f"📄 Job file uploaded: {file.filename}")
            
            try:
                # Save the file temporarily
                os.makedirs(app.config['JOB_DESC_FOLDER'], exist_ok=True)
                file_path = os.path.join(app.config['JOB_DESC_FOLDER'], file.filename)
                file.save(file_path)
                print(f"   ✓ File saved")
                
                # Extract text from PDF
                print(f"   📖 Extracting text from PDF...")
                job_description = parser.extract_text_from_pdf(file_path)
                
                if job_description:
                    print(f"   ✅ Extracted {len(job_description)} characters from PDF")
                else:
                    print(f"   ❌ Failed to extract text from PDF")
                    
            except Exception as e:
                print(f"   ❌ Error processing job file: {e}")
    
    # If no file or extraction failed, use textarea input
    if not job_description:
        job_description = request.form.get('job_description', '').strip()
        if job_description:
            print(f"📋 Using manual text input: {len(job_description)} chars")
    
    # Validate
    if not job_title:
        flash("Job title is required.", "warning")
        return redirect(url_for('jobs_page'))
    
    if not job_description or len(job_description.strip()) < 20:
        flash("Job description is required (minimum 20 characters).", "warning")
        return redirect(url_for('jobs_page'))
    
    # Create job object
    job = {
        'id': str(uuid.uuid4()),
        'title': job_title,
        'description': job_description,
        'created_at': datetime.now().isoformat(),
        'selected': False
    }
    
    # Load existing jobs and add new one
    jobs = load_jobs()
    jobs.append(job)
    save_jobs(jobs)
    
    print(f"✅ Job added: {job_title}")
    print("=" * 70 + "\n")
    
    flash(f"✅ Job '{job_title}' added successfully!", "success")
    return redirect(url_for('jobs_page'))

@app.route('/api/jobs/select/<job_id>', methods=['POST'])
def select_job(job_id):
    """Select a job for matching"""
    try:
        jobs = load_jobs()
        
        # Deselect all, select this one
        for job in jobs:
            job['selected'] = (job['id'] == job_id)
        
        save_jobs(jobs)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs/delete/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    """Delete a job description"""
    try:
        jobs = load_jobs()
        jobs = [job for job in jobs if job['id'] != job_id]
        save_jobs(jobs)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs/delete-all', methods=['DELETE'])
def delete_all_jobs():
    """Delete all job descriptions"""
    try:
        save_jobs([])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs/view/<job_id>')
def view_job(job_id):
    """View job details"""
    try:
        jobs = load_jobs()
        job = next((j for j in jobs if j['id'] == job_id), None)
        if job:
            return jsonify(job)
        return jsonify({'error': 'Job not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# MATCHING OPERATION - TWO-PHASE CONSISTENT MATCHING
# =====================================================

@app.route('/match-and-results')
def match_and_show_results():
    """Perform matching and show results with CONSISTENT requirements"""
    print("\n" + "=" * 70)
    print("🎯 MATCH REQUEST")
    print("=" * 70)
    
    # Get selected job
    selected_job = get_selected_job()
    
    if not selected_job:
        flash("Please select a job description first.", "warning")
        return redirect(url_for('jobs_page'))
    
    job_description = selected_job['description']
    job_title = selected_job['title']
    
    print(f"📋 Job: {job_title}")
    print(f"📋 Description: {len(job_description)} chars")
    
    # Check for parsed resumes
    parsed_dir = app.config['PARSED_FOLDER']
    
    if not os.path.exists(parsed_dir) or not os.listdir(parsed_dir):
        print("❌ No parsed resumes")
        flash("Please upload resumes first.", "warning")
        return redirect(url_for('resumes_page'))
    
    resume_files = os.listdir(parsed_dir)
    print(f"📊 Resumes: {len(resume_files)}")

    # ============================================
    # PHASE 1: Extract job requirements ONCE
    # ============================================
    print("\n" + "=" * 70)
    print("📋 PHASE 1: EXTRACTING JOB REQUIREMENTS")
    print("=" * 70)
    
    job_requirements = matcher.extract_job_requirements(job_description)
    
    if not job_requirements:
        print("❌ Failed to extract job requirements")
        flash("Error analyzing job description. Please try again.", "danger")
        return redirect(url_for('jobs_page'))
    
    required_skills = job_requirements.get('required_skills', [])
    print(f"✅ Found {len(required_skills)} required skills")
    print(f"📋 Skills: {', '.join(required_skills[:5])}{'...' if len(required_skills) > 5 else ''}")
    print(f"💼 Experience: {job_requirements.get('experience_requirement', 'Not specified')}")
    print(f"🎓 Education: {job_requirements.get('education_requirement', 'Not specified')}")
    print("=" * 70)
    
    # ============================================
    # PHASE 2: Match each candidate against SAME requirements
    # ============================================
    print("\n" + "=" * 70)
    print(f"🔍 PHASE 2: MATCHING {len(resume_files)} CANDIDATES")
    print("=" * 70)
    
    match_results = []
    
    for idx, json_file in enumerate(resume_files, 1):
        print(f"\n[{idx}/{len(resume_files)}] Matching: {json_file}")
        try:
            with open(os.path.join(parsed_dir, json_file), 'r', encoding='utf-8') as f:
                resume_data = json.load(f)
                candidate_name = resume_data.get('name', json_file.replace('.pdf.json', ''))
                print(f"   👤 Candidate: {candidate_name}")
                print(f"   🤖 Calling AI matcher...")
                
                # Pass job_requirements for CONSISTENT matching
                analysis = matcher.match_resume_to_job(
                    resume_data, 
                    job_description, 
                    job_requirements  # ← CRITICAL: Use same requirements for all
                )
                
                if analysis:
                    score = analysis.get('match_score', 0)
                    matched = len(analysis.get('matched_skills', []))
                    total = len(required_skills)
                    
                    print(f"   ✅ Score: {score}% ({matched}/{total} skills)")
                    
                    # Add metadata
                    analysis['candidate_name'] = candidate_name
                    analysis['resume_id'] = candidate_name  # Use name as ID for view button
                    analysis['filename'] = json_file
                    
                    match_results.append(analysis)
                else:
                    print(f"   ❌ Matching failed - AI returned None")
                    
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\n📊 Successfully matched: {len(match_results)}/{len(resume_files)}")
    
    # ============================================
    # PHASE 3: Rank and select top matches
    # ============================================
    print("\n" + "=" * 70)
    print("🏆 PHASE 3: RANKING CANDIDATES")
    print("=" * 70)
    
    # Rank all matches (top 3)
    top_matches = matcher.rank_resumes(match_results)
    
    print(f"✅ Top {len(top_matches)} candidates selected:")
    for i, match in enumerate(top_matches, 1):
        matched_skills = len(match.get('matched_skills', []))
        total_skills = len(required_skills)
        print(f"   #{i}. {match['candidate_name']} - {match['match_score']}% ({matched_skills}/{total_skills} skills)")
    
    print("=" * 70 + "\n")
    
    # Store in session
    session['match_results'] = top_matches
    session['job_title'] = job_title
    session['job_description'] = job_description
    
    if len(top_matches) == 0:
        flash("No suitable matches found for this job description.", "info")
    else:
        flash(f"✅ Found {len(top_matches)} matching candidates! All evaluated against {len(required_skills)} required skills.", "success")
    
    return redirect(url_for('results_page'))

# =====================================================
# ERROR HANDLERS
# =====================================================

@app.errorhandler(413)
def too_large(e):
    flash("File is too large! Maximum size is 16MB.", "danger")
    return redirect(request.referrer or url_for('resumes_page'))

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

# =====================================================
# MAIN
# =====================================================

if __name__ == '__main__':
    # Ensure folders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['JOB_DESC_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PARSED_FOLDER'], exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    print("\n" + "=" * 70)
    print("🚀 STARTING CANDIDATE INSIGHTS SYSTEM")
    print("=" * 70)
    print(f"📁 Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"📁 Job desc folder: {app.config['JOB_DESC_FOLDER']}")
    print(f"📁 Parsed folder: {app.config['PARSED_FOLDER']}")
    print(f"📁 Jobs data: {app.config['JOBS_DATA_FILE']}")
    print(f"📋 Accepted formats: PDF only")
    print("=" * 70 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)