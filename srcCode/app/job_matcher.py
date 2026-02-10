from openai import OpenAI
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json

class JobMatcher:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        self.cached_requirements = None  # Cache requirements for consistency
    
    def extract_job_requirements(self, job_description):
        """Extract requirements from job description ONCE for consistent matching"""
        
        print("   🔍 Extracting job requirements...")
        
        prompt = f"""
        You are an expert HR analyst. Extract the EXACT requirements from this job description.
        
        Job Description:
        {job_description}
        
        Extract and return in JSON format:
        {{
            "required_skills": ["list of ALL required technical and soft skills"],
            "experience_requirement": "years and type of experience required (e.g., '2+ years mobile development')",
            "education_requirement": "degree and field required (e.g., 'Bachelor in Computer Science')"
        }}
        
        CRITICAL RULES:
        1. Extract ALL skills mentioned in the job description
        2. Include both technical skills (Flutter, Dart) AND soft skills (teamwork, problem-solving)
        3. Be comprehensive - don't miss any skills
        4. Translate to English if job is in Arabic
        5. Use the EXACT same list for ALL candidates
        
        Return ONLY valid JSON, no markdown.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an HR analyst who extracts job requirements comprehensively and accurately. Return only valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0  # Deterministic
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            requirements = json.loads(response_text)
            
            # Cache for consistency
            self.cached_requirements = requirements
            
            print(f"   ✅ Extracted {len(requirements.get('required_skills', []))} required skills")
            print(f"   📋 Skills: {', '.join(requirements.get('required_skills', [])[:5])}...")
            
            return requirements
            
        except Exception as e:
            print(f"   ❌ Error extracting requirements: {e}")
            return None
    
    def match_resume_to_job(self, parsed_resume, job_description, job_requirements=None):
        """Match a single resume to a job description using CONSISTENT requirements with DETAILED feedback"""
        
        resume_text = json.dumps(parsed_resume, ensure_ascii=False, indent=2)
        
        # Use cached requirements if available, otherwise extract
        if job_requirements is None:
            if self.cached_requirements is None:
                job_requirements = self.extract_job_requirements(job_description)
            else:
                job_requirements = self.cached_requirements
        
        if job_requirements is None:
            print("   ❌ Could not extract job requirements")
            return None
        
        total_skills = len(job_requirements.get('required_skills', []))
        
        prompt = f"""
        You are an expert HR analyst performing candidate evaluation.

        GENDER-NEUTRAL EVALUATION REQUIREMENT:
        Evaluate this CV based solely on qualifications, experience, and skills. Ignore any indicators of gender, such as names, pronouns, or gendered language. Do not make assumptions about career gaps, job preferences, or capabilities based on perceived gender. Focus exclusively on merit-based criteria and apply identical standards to all candidates.
        
        CRITICAL: You are given PRE-EXTRACTED job requirements. Use EXACTLY these requirements.
        DO NOT extract requirements again. DO NOT add or remove skills from the list.
        
        JOB REQUIREMENTS (USE EXACTLY AS PROVIDED):
        Required Skills: {job_requirements.get('required_skills', [])}
        Experience Required: {job_requirements.get('experience_requirement', 'Not specified')}
        Education Required: {job_requirements.get('education_requirement', 'Not specified')}
        
        CANDIDATE RESUME:
        {resume_text}
        
        MATCHING INSTRUCTIONS:

        Step 1: COMPARE SKILLS
        - Go through each skill in the required_skills list ({total_skills} skills total)
        - Check if the candidate has this skill (exact or similar)
        - Count matches and misses
        
        Step 2: COMPARE EXPERIENCE (BE SPECIFIC!)
        - Extract candidate's EXACT years of experience from resume
        - Compare with required experience: {job_requirements.get('experience_requirement', 'Not specified')}
        - CRITICAL: Use correct starting phrase based on comparison
        - Format examples:
          ✅ "Meets requirements: Has 3 years of mobile development, exceeding the 2+ years required"
          ✅ "Meets requirements: Has 2 years of mobile development, meeting the 2+ years required"
          ✅ "Does not meet: Has 1 year of experience, below the 2+ years required"
          ✅ "Does not meet: No relevant experience mentioned in resume"
        
        Step 3: COMPARE EDUCATION (BE SPECIFIC!)
        - Extract candidate's education from resume
        - Compare with required: {job_requirements.get('education_requirement', 'Not specified')}
        - CRITICAL: State what candidate HAS (or "not mentioned")
        - Format examples:
          ✅ "Has Bachelor's in Computer Science, matching the requirement"
          ✅ "Has Diploma in IT, below the required Bachelor's degree"
          ✅ "No education mentioned in resume"
        
        Step 4: CALCULATE SCORE (SHOW EXACT MATH!)
        - Skills: (matched / {total_skills}) * 40 = X points
        - Experience: Y points (0-35 based on match)
        - Education: Z points (0-25 based on match)
        - TOTAL: X + Y + Z = FINAL SCORE
        
        SCORING DETAILS:
        
        Skills Points (0-40):
        - Formula: (matched_skills / {total_skills}) * 40
        - Example: 7/{total_skills} = {round(7/total_skills*100 if total_skills > 0 else 0)}% × 40 = {round(7/total_skills*40 if total_skills > 0 else 0)} points
        
        Experience Points (0-35):
        - Exceeds requirements significantly = 35 points
        - Meets exactly or exceeds slightly = 30-32 points
        - Somewhat below = 18-25 points
        - Far below or no experience = 10-15 points
        
        Education Points (0-25):
        - Exceeds (Master's for Bachelor's) = 25 points
        - Meets exactly = 25 points
        - Close (Diploma for Bachelor's) = 15-18 points
        - No education mentioned = 10 points
        
        Return analysis in JSON format:
        {{
            "total_required_skills": {total_skills},
            "match_score": <0-100>,
            "matched_skills": ["skills from required list that candidate has"],
            "missing_skills": ["skills from required list that candidate lacks"],
            "experience_match": "CRITICAL FORMAT - Choose EXACTLY ONE based on comparison:
                - If candidate EXCEEDS or MEETS requirement: 'Meets requirements: Has [X years], [exceeding/meeting] the [Y]+ years required'
                - If candidate is BELOW requirement: 'Does not meet: Has [X years], below the [Y]+ years required'
                - If no experience: 'Does not meet: No relevant experience mentioned in resume'
                WRONG: 'Meets requirements: Has 1 year, below...' (contradictory!)
                RIGHT: 'Does not meet: Has 1 year, below the 2+ years required'",
            "education_match": "MUST start with: 'Meets requirements: Has [specific degree]...' OR 'Acceptable education: Has [specific degree]...' OR 'Does not meet: Has [specific degree or 'not mentioned']...'",
            "overall_explanation": "CRITICAL: DO NOT use candidate's name. Start with 'This candidate...' or 'Strong/Good/Fair match...' Explain score WITHOUT names.",
            "score_breakdown": {{
                "skills_points": <0-40>,
                "experience_points": <0-35>,
                "education_points": <0-25>,
                "calculation": "skills_points + experience_points + education_points = match_score"
            }}
        }}
        
        CRITICAL RULES:
        1. total_required_skills MUST be {total_skills}
        2. matched_skills + missing_skills = {total_skills}
        3. ALWAYS state candidate's actual years of experience (or "not mentioned")
        4. ALWAYS state candidate's actual education (or "not mentioned")
        5. NEVER use candidate's name in overall_explanation
        6. score_breakdown must show exact points for each category
        7. Final match_score must equal skills_points + experience_points + education_points
        
        Return ONLY valid JSON.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": """You are an HR analyst who provides DETAILED, SPECIFIC matching results.

CRITICAL RULES:
1. ALWAYS mention candidate's exact years of experience
2. ALWAYS mention candidate's specific education (or state "not mentioned")
3. NEVER use candidate's name in overall_explanation
4. SHOW exact score calculation with points breakdown
5. Use the EXACT requirements provided, don't modify them

You are detailed, specific, and mathematically precise."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1  # Very low for consistency
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            match_result = json.loads(response_text)
            
            # Validation
            required_fields = ['match_score', 'matched_skills', 'missing_skills', 
                             'experience_match', 'education_match', 'overall_explanation']
            for field in required_fields:
                if field not in match_result:
                    print(f"   ⚠️  Warning: Missing field '{field}'")
                    match_result[field] = "N/A" if field != 'match_score' else 0
                    if field in ['matched_skills', 'missing_skills']:
                        match_result[field] = []
            
            match_result['match_score'] = int(match_result['match_score'])
            
            # POST-PROCESS: Fix math if AI got it wrong
            if 'score_breakdown' in match_result:
                breakdown = match_result['score_breakdown']
                skills_pts = int(breakdown.get('skills_points', 0))
                exp_pts = int(breakdown.get('experience_points', 0))
                edu_pts = int(breakdown.get('education_points', 0))
                calculated_total = skills_pts + exp_pts + edu_pts
                
                # If AI got the math wrong, fix it
                if calculated_total != match_result['match_score']:
                    print(f"   ⚠️  Math error detected! AI said {match_result['match_score']}%, actual is {calculated_total}%")
                    print(f"      Correcting: {skills_pts} + {exp_pts} + {edu_pts} = {calculated_total}%")
                    match_result['match_score'] = calculated_total
                    breakdown['calculation'] = f"{skills_pts} + {exp_pts} + {edu_pts} = {calculated_total}"
            
            # Verify consistency
            reported_total = match_result.get('total_required_skills', 0)
            if reported_total != total_skills:
                print(f"   ⚠️  Skill count mismatch! Expected {total_skills}, got {reported_total}")
            
            # Log breakdown for transparency
            if 'score_breakdown' in match_result:
                breakdown = match_result['score_breakdown']
                skills_pts = breakdown.get('skills_points', 0)
                exp_pts = breakdown.get('experience_points', 0)
                edu_pts = breakdown.get('education_points', 0)
                total_pts = skills_pts + exp_pts + edu_pts
                
                print(f"   📊 Score Breakdown:")
                print(f"      Skills: {len(match_result.get('matched_skills', []))}/{total_skills} = {skills_pts}/40 pts")
                print(f"      Experience: {exp_pts}/35 pts")
                print(f"      Education: {edu_pts}/25 pts")
                print(f"      ✅ TOTAL: {total_pts}% (reported: {match_result['match_score']}%)")
                
                # Verify math
                if total_pts != match_result['match_score']:
                    print(f"   ⚠️  Math error detected! {total_pts} ≠ {match_result['match_score']}")
            else:
                print(f"   📊 Skills: {len(match_result.get('matched_skills', []))}/{total_skills} matched")
            
            return match_result
            
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parsing error: {e}")
            print(f"   📄 Response: {response_text[:500]}...")
            return None
        except Exception as e:
            print(f"   ❌ Error matching resume: {e}")
            return None
    
    def rank_resumes(self, match_results):
        """Rank resumes by match score and return top 3"""
        if not match_results:
            return []
        
        # Sort by match score (highest first)
        sorted_results = sorted(
            match_results, 
            key=lambda x: x.get('match_score', 0), 
            reverse=True
        )
        
        # Return top 3
        return sorted_results[:3]